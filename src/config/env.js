import dotenv from 'dotenv';
dotenv.config();

export const config = {
  port: process.env.PORT || 8080,
  googleApiKey: process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY,
  geminiModel: process.env.GEMINI_MODEL || 'gemini-2.0-flash-001',
  cors: {
    // ajusta origins en prod
    origin: true,
    credentials: true
  }
};

if (!config.googleApiKey) {
  console.warn('[WARN] GOOGLE_API_KEY/GEMINI_API_KEY no está definido en .env');
}
