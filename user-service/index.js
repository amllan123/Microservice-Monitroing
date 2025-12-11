// index.js
const express = require("express");
const app = express();
const PORT = 3000;

// Middleware
app.use(express.json());

// Mock in-memory users
let users = [
  { id: 1, name: "John Doe", email: "john@example.com" },
  { id: 2, name: "Jane Smith", email: "jane@example.com" },
];

// =========================
//      User Routes
// =========================

// GET all users
app.get("/api/users", (req, res) => {
  res.json(users);
});

// GET user by ID
app.get("/api/users/:id", (req, res) => {
  const userId = Number(req.params.id);
  const user = users.find((u) => u.id === userId);

  if (!user) return res.status(404).json({ message: "User not found" });

  res.json(user);
});

// CREATE new user
app.post("/api/users", (req, res) => {
  const { name, email } = req.body;

  if (!name || !email)
    return res.status(400).json({ message: "Name and email required" });

  const newUser = {
    id: users.length + 1,
    name,
    email,
  };

  users.push(newUser);
  res.status(201).json(newUser);
});

// UPDATE user
app.put("/api/users/:id", (req, res) => {
  const userId = Number(req.params.id);
  const { name, email } = req.body;

  const user = users.find((u) => u.id === userId);
  if (!user) return res.status(404).json({ message: "User not found" });

  if (name) user.name = name;
  if (email) user.email = email;

  res.json(user);
});

// DELETE user
app.delete("/api/users/:id", (req, res) => {
  const userId = Number(req.params.id);

  users = users.filter((u) => u.id !== userId);

  res.json({ message: "User deleted successfully" });
});

// Start server
app.listen(PORT, () => {
  console.log(`User service running at http://localhost:${PORT}`);
});
