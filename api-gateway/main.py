from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import httpx
import os
import time
import redis.asyncio as redis

from opentelemetry import trace, metrics
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response


USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', 'http://localhost:3000')
DRIVER_SERVICE_URL = os.getenv('DRIVER_SERVICE_URL', 'http://localhost:8001')
RIDE_SERVICE_URL = os.getenv('RIDE_SERVICE_URL', 'http://localhost:3002')
PAYMENT_SERVICE_URL = os.getenv('PAYMENT_SERVICE_URL', 'http://localhost:3003')
NOTIFICATION_SERVICE_URL = os.getenv('NOTIFICATION_SERVICE_URL', 'http://localhost:8002')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
OTEL_ENDPOINT = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4318')


# Resource configuration
resource = Resource.create({
    "service.name": "api-gateway",
    "service.version": "1.0.0"
})

# Trace configuration
trace_provider = TracerProvider(resource=resource)
trace_exporter = OTLPSpanExporter(endpoint=f"{OTEL_ENDPOINT}/v1/traces")
span_processor = BatchSpanProcessor(trace_exporter)
trace_provider.add_span_processor(span_processor)
trace.set_tracer_provider(trace_provider)
tracer = trace.get_tracer(__name__)

# Metrics configuration
metric_exporter = OTLPMetricExporter(endpoint=f"{OTEL_ENDPOINT}/v1/metrics")
metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=10000)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter(__name__)


def get_base_endpoint(path: str) -> str:
    """Extract base endpoint: /api/users/123 -> /api/users"""
    parts = path.split('/')
    if len(parts) >= 3 and parts[1] == 'api':
        return f"/{parts[1]}/{parts[2]}"
    return path


# Prometheus metrics
REQUEST_COUNT = Counter('gateway_http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('gateway_http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])
RATE_LIMIT_HITS = Counter('gateway_rate_limit_hits_total', 'Rate limit hits', ['client_ip'])
ACTIVE_REQUESTS = Gauge('gateway_active_requests', 'Active requests')

# Create FastAPI app
app = FastAPI(title="Uber API Gateway", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument BEFORE app starts - DO THIS BEFORE STARTUP EVENT
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()
RedisInstrumentor().instrument()

redis_client = None
http_client = None

@app.on_event("startup")
async def startup_event():
    global redis_client, http_client
    redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    http_client = httpx.AsyncClient(timeout=30.0)
    
    print("✅ API Gateway started successfully")
    print(f"📊 Sending traces to: {OTEL_ENDPOINT}/v1/traces")

@app.on_event("shutdown")
async def shutdown_event():
    await redis_client.close()
    await http_client.aclose()
    # Flush any pending spans
    trace_provider.force_flush()

async def rate_limiter(request: Request):
    client_ip = request.client.host
    key = f"ratelimit:{client_ip}:{request.url.path}"
    with tracer.start_as_current_span("rate_limit_check") as span:
        span.set_attribute("client.ip", client_ip)
        span.set_attribute("rate_limit.key", key)
        
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 60)
        
        span.set_attribute("rate_limit.count", count)
        
        if count > 100:
            RATE_LIMIT_HITS.labels(client_ip=client_ip).inc()
            span.set_attribute("rate_limit.exceeded", True)
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

# Middleware for metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    ACTIVE_REQUESTS.inc()
    start_time = time.time()
    
    # Get base endpoint for grouping
    base_endpoint = get_base_endpoint(request.url.path)
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=base_endpoint,  # CHANGED: Use base endpoint
            status=response.status_code
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=base_endpoint  # CHANGED: Use base endpoint
        ).observe(duration)
        
        return response
    finally:
        ACTIVE_REQUESTS.dec()


async def proxy_request(service_url: str, path: str, request: Request):
    url = f"{service_url}{path}"
    headers = dict(request.headers)
    headers.pop('host', None)
    
    with tracer.start_as_current_span(f"proxy_request") as span:
        span.set_attribute("http.url", url)
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.target", path)
        span.set_attribute("service.url", service_url)

        try:
            if request.method == "GET":
                response = await http_client.get(url, headers=headers, params=request.query_params)
            elif request.method == "POST":
                body = await request.body()
                response = await http_client.post(url, headers=headers, content=body)
            elif request.method == "PUT":
                body = await request.body()
                response = await http_client.put(url, headers=headers, content=body)
            elif request.method == "DELETE":
                response = await http_client.delete(url, headers=headers)
            else:
                raise HTTPException(status_code=405, detail="Method not allowed")
            
            span.set_attribute("http.status_code", response.status_code)
            return JSONResponse(content=response.json(), status_code=response.status_code)
        
        except httpx.RequestError as e:
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway"}

# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics_endpoint():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ==================== Routes ====================

@app.api_route("/api/users/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def user_service_proxy(path: str, request: Request, _: None = Depends(rate_limiter)):
    return await proxy_request(USER_SERVICE_URL, f"/api/users/{path}", request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)