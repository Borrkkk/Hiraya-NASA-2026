import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getProfile, profiles } from "@/lib/profiles";
import { ProfileScreen } from "../profile-screen";

type Props = { params: Promise<{ id: string }> };

export function generateStaticParams() {
  return profiles.map(({ id }) => ({ id }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const profile = getProfile((await params).id);
  return { title: profile ? `${profile.name} · Pulsr` : "Profile not found · Pulsr" };
}

export default async function UserProfilePage({ params }: Props) {
  const profile = getProfile((await params).id);
  if (!profile) notFound();
  return <ProfileScreen profile={profile} />;
}
