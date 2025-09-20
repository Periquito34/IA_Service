import { GoogleGenAI } from '@google/genai';
import { config } from '../config/env.js';

const ai = new GoogleGenAI({ apiKey: config.googleApiKey });

function toContents(messages = []) {
  return messages.map((m) => ({
    role: m.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: m.content }]
  }));
}

export async function* streamChat({ messages = [], system }) {
  const contents = toContents(messages);
  if (system) contents.unshift({ role: 'user', parts: [{ text: `SYSTEM:\n${system}` }] });

  const stream = await ai.models.generateContentStream({
    model: config.geminiModel,
    contents
  });

  for await (const chunk of stream) {
    // chunk.text existe cuando hay tokens; si safety bloquea, puede venir vacío
    const text = chunk?.text ?? '';
    if (text) yield text;
  }
}

export async function chatOnce({ messages = [], system }) {
  const contents = toContents(messages);
  if (system) contents.unshift({ role: 'user', parts: [{ text: `SYSTEM:\n${system}` }] });

  const result = await ai.models.generateContent({
    model: config.geminiModel,
    contents
  });

  // Distintas formas de acceso según el resultado:
  const text =
    // 1) algunas versiones exponen 'text' directo
    result?.text ??
    // 2) otras usan 'response.text()'
    (result?.response && typeof result.response.text === 'function' ? result.response.text() : undefined) ??
    // 3) fallback manual a candidates/parts
    (Array.isArray(result?.candidates)
      ? result.candidates
          .flatMap(c => c?.content?.parts ?? [])
          .map(p => p?.text ?? '')
          .join('')
      : '');

  // Si quedó vacío, intenta dar un mensaje más claro
  if (!text) {
    // Puede ser bloqueo de seguridad u otro motivo:
    const safety = result?.candidates?.[0]?.safetyRatings ?? result?.safetyRatings;
    const reasons = Array.isArray(safety)
      ? safety.map(r => `${r.category}:${r.probability}`).join(', ')
      : 'unknown';

    throw Object.assign(new Error('La respuesta llegó vacía o fue bloqueada por safety.'), {
      status: 400,
      details: { reasons, raw: result }
    });
  }

  return text;
}
