import express from "express";
import {
  analyze,
  chat,
  getGlossary
} from "../src/controllers/intelligence.controller.js";

const router = express.Router();

router.post("/analyze", analyze);
router.post("/chat", chat);
router.get("/glossary", getGlossary);

export default router;