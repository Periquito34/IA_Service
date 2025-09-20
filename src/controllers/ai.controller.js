import { initSSE } from '../utils/sse.js';
import { streamChat, chatOnce } from '../services/gemini.service.js';

export async function chatStreamCtrl(req, res) {
  const { messages = [], system } = req.body || {};
  const sse = initSSE(res);

  try {
    if (!Array.isArray(messages) || messages.length === 0) {
      sse.event('error', { message: 'messages[] requerido' });
      return sse.close();
    }

    for await (const token of streamChat({ messages, system })) {
      sse.send({ token });
    }
    sse.event('done', {});
    sse.close();
  } catch (err) {
    sse.event('error', { message: err.message, details: err.details ?? null });
    sse.close();
  }
}

export async function chatOnceCtrl(req, res, next) {
  try {
    const { messages = [], system } = req.body || {};
    if (!Array.isArray(messages) || messages.length === 0) {
      return res.status(400).json({ error: 'messages[] requerido' });
    }
    const text = await chatOnce({ messages, system });
    res.json({ text });
  } catch (err) {
    // si viene con status, úsalo
    res.status(err.status ?? 500).json({
      error: err.message ?? 'Internal Server Error',
      details: err.details ?? null
    });
  }
}
