"use client";
import Link from 'next/link';
import { HomeHeader } from '@/components/home/header';
import { SkyImage } from '@/components/ui';
import { PostDiscussion } from './post-discussion';
import { getProfile, type ObservationPost } from '@/lib/profiles';
import { getObject } from '@/lib/sky/catalog';
import { exploreHref } from '@/lib/explore/href';

export function NotebookThread({ post }: { post: ObservationPost }) {
  const object = getObject(post.objectId);
  return <div className="min-h-dvh bg-ground"><HomeHeader /><main className="mx-auto flex max-w-3xl flex-col gap-5 px-6 py-8">
    <h1 className="text-h1">{post.title}</h1>
    <p className="text-small text-ink-secondary">{getProfile(post.authorId)?.name} · {post.dateLabel}</p>
    <SkyImage cutout={post.cutout} alt={`Reference observation of ${object.name}`} className="aspect-[2/1] rounded-xl" sizes="720px" />
    <p className="text-body leading-relaxed">{post.body}</p>
    <p className="text-small text-ink-secondary">{post.note}</p>
    <PostDiscussion postId={post.id} postTitle={post.title} inline />
    <Link href={exploreHref({ q: object.name, ra: object.ra, dec: object.dec, fov: post.fov ?? object.fov })} className="w-fit text-small underline">Explore this region separately ↗</Link>
    <p className="text-caption text-ink-secondary">Demo notebook conversation. Replies in this older notebook thread are saved in this browser.</p>
  </main></div>;
}
