"use client";
import { useQuery } from '@tanstack/react-query';
import { api } from './api';

export function useAccount() {
  return useQuery({ queryKey: ['current-account'], queryFn: () => api<{
    account: { id: string; name: string; mode: string }; ai_available: boolean;
  }>('/explore/session'), staleTime: 60000 });
}
