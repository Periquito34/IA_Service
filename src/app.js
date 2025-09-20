import express from 'express';
import cors from 'cors';
import aiRoutes from './routes/ai.routes.js';
import { errorHandler } from './middlewares/errorHandler.js';
import { config } from './config/env.js';

const app = express();

app.use(cors(config.cors));
app.use(express.json());

app.get('/', (_req, res) => res.send('AI Service OK'));
app.use('/ai', aiRoutes);

// manejo de errores al final
app.use(errorHandler);

export default app;
