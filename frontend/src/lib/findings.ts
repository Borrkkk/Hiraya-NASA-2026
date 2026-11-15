import type { SkyBox } from './explore/types';
import type { Spectrum } from './explore/types';

export type Finding = {
  id: string; title: string; body: string; author: string; created_at: string;
  box: SkyBox; status: 'suspected-motion';
  evidence: { bands: string[]; epochs: string[]; track: { ra: number; dec: number; epochId: string; date: string }[]; view?: { ra: number; dec: number; fov: number } | null;
    sample?: boolean; authorId?: string; summary?: string; summaryMethod?: 'data' | 'ai';
    image?: { url: string; caption: string; date: string; detector: number; wavelengthUm: number; band: string; extentDeg: number; contextUrl?: string };
    animation?: { url: string; frameCount: number; caption: string; frames: { date: string; epochId: string; wavelengthUm: number }[] };
    spectrum?: Spectrum;
    observationFacts?: { firstDate: string; lastDate: string; detectors: number[]; measurementCount: number; epochCount: number };
    sourceReference?: { ra: number; dec: number; method: string; positions: { ra: number; dec: number; epochId: string; detector: number }[] };
  };
};
export type FindingComment = { id: string; author: string; body: string; created_at: string };
export const regionQuery = (box: SkyBox) => new URLSearchParams({
  ra: String(box.ra), dec: String(box.dec), width: String(box.width), height: String(box.height),
}).toString();
