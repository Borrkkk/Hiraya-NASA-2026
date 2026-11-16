"use client";

import { DEMO_ACCOUNT } from "./community";

// There is no sign-in in the preview: everyone is the same demo profile.
export function useAccount() {
  return { data: { account: DEMO_ACCOUNT, ai_available: false } as const };
}
