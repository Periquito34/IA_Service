import { Router } from 'express';
import { chatStreamCtrl, chatOnceCtrl } from '../controllers/ai.controller.js';

const r = Router();

// POST /ai/chat-stream  -> SSE
r.post('/chat-stream', chatStreamCtrl);

// POST /ai/chat         -> respuesta única (útil para Postman)
r.post('/chat', chatOnceCtrl);

export default r;
