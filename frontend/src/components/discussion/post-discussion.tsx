"use client";

import Link from "next/link";
import { useId, useRef, useState, type FormEvent } from "react";
import { BadgeCheck, ChevronDown, MessageCircle, Reply, Send, X } from "lucide-react";
import { Avatar } from "@/components/ui";
import { addComment, useDiscussion, type DiscussionComment } from "@/lib/discussions";
import { currentUserId, getProfile, profileHref } from "@/lib/profiles";

export function PostDiscussion({ postId, postTitle, inline = false }: { postId: string; postTitle: string; inline?: boolean }) {
  const comments = useDiscussion(postId);
  const [open, setOpen] = useState(inline);
  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<DiscussionComment | null>(null);
  const [error, setError] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const textarea = useRef<HTMLTextAreaElement>(null);
  const panelId = useId();
  const composerId = useId();
  const currentUser = getProfile(currentUserId)!;
  const rootComments = comments.filter((comment) => comment.parentId === null);
  const replies = (id: string) => comments.filter((comment) => comment.parentId === id);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      addComment(postId, draft, replyTo ? replyTo.parentId ?? replyTo.id : null);
      setDraft("");
      setReplyTo(null);
      setAnnouncement("Comment posted and saved in this browser.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not post your comment. Please retry.");
    }
  }

  function reply(comment: DiscussionComment) {
    setReplyTo(comment);
    setError("");
    setAnnouncement("");
    textarea.current?.focus();
  }

  function renderComment(comment: DiscussionComment) {
    const author = getProfile(comment.authorId)!;
    return <div className="flex min-w-0 gap-2.5">
      <Link href={profileHref(author.id)} aria-label={`View ${author.name}’s profile`} className="h-fit shrink-0 rounded-full">
        <Avatar initials={author.initials} tone={author.tone} size="sm" className="mt-1" />
      </Link>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Link href={profileHref(author.id)} className="rounded-xs text-small font-medium text-ink hover:underline">{author.name}</Link>
          {author.verified && <BadgeCheck size={13} className="text-explained" aria-label="Verified researcher" />}
          <time dateTime={comment.createdAt} className="font-mono text-mono-sm text-ink-muted">{comment.createdAt.slice(0, 10)} · {comment.createdAt.slice(11, 16)} UTC</time>
        </div>
        <p className="mt-1 whitespace-pre-wrap break-words text-small leading-relaxed text-ink-secondary [overflow-wrap:anywhere]">{comment.body}</p>
        <button type="button" onClick={() => reply(comment)} aria-label={`Reply to ${author.name}: ${comment.body.slice(0, 50)}`} className="mt-1 inline-flex min-h-8 cursor-pointer items-center gap-1.5 rounded-xs text-caption text-ink-muted hover:text-ink">
          <Reply size={12} aria-hidden="true" /> Reply
        </button>
      </div>
    </div>;
  }

  if (!inline) return <Link href={`/findings/${postId}`} aria-label={`Discussion on ${postTitle}: ${comments.length} comments`} className="relative z-10 mt-4 inline-flex min-h-10 items-center gap-2 border-t border-line pt-3 text-small text-ink-secondary hover:text-ink"><MessageCircle size={16} aria-hidden="true" />Discussion <span className="font-mono">{comments.length}</span></Link>;

  return <div className="relative z-10 mt-4 border-t border-line pt-3">
    <button type="button" aria-expanded={open} aria-controls={panelId} aria-label={`Discussion on ${postTitle}: ${comments.length} comments`} onClick={() => setOpen((value) => !value)} className="flex min-h-10 w-full cursor-pointer items-center gap-2 rounded-md text-small text-ink-secondary hover:text-ink">
      <MessageCircle size={16} aria-hidden="true" />
      <span>Discussion</span>
      <span className="rounded-sm bg-ground px-1.5 py-0.5 font-mono text-mono-sm tabular-nums">{comments.length}</span>
      <ChevronDown size={14} aria-hidden="true" className={`ml-auto transition-transform ${open ? 'rotate-180' : ''}`} />
    </button>
    {open && <section id={panelId} aria-label={`Discussion on ${postTitle}`} className="pt-3">
      {comments.length > 0 ? <ol className="flex flex-col gap-5">
        {rootComments.map((comment) => <li key={comment.id}>
          {renderComment(comment)}
          {replies(comment.id).length > 0 && <ol className="ml-2.5 mt-3 flex flex-col gap-4 border-l border-line-strong pl-4 sm:ml-5 sm:pl-5">
            {replies(comment.id).map((answer) => <li key={answer.id}>{renderComment(answer)}</li>)}
          </ol>}
        </li>)}
      </ol> : <div className="rounded-md border border-dashed border-line-strong p-4"><p className="text-small text-ink">Start the discussion</p><p className="mt-1 text-caption text-ink-secondary">Ask a question, share a comparison, or add context to this observation.</p></div>}
      <form onSubmit={submit} className="mt-5 rounded-md border border-line-strong bg-ground p-3">
        <div className="mb-3 flex items-center gap-2"><Avatar initials={currentUser.initials} tone={currentUser.tone} size="sm" /><span className="text-caption text-ink-secondary">Commenting as <Link href={profileHref(currentUser.id)} className="text-ink hover:underline">{currentUser.name}</Link></span></div>
        {replyTo && <div className="mb-2 flex items-center justify-between gap-2 rounded-sm bg-raised px-2 py-1 text-caption text-ink-secondary"><span>Replying to {getProfile(replyTo.authorId)?.name}</span><button type="button" aria-label="Cancel reply" onClick={() => setReplyTo(null)} className="grid size-7 shrink-0 cursor-pointer place-items-center rounded-xs hover:text-ink"><X size={13} /></button></div>}
        <label htmlFor={composerId} className="sr-only">{replyTo ? 'Write a reply' : 'Write a comment'}</label>
        <textarea id={composerId} ref={textarea} value={draft} onChange={(event) => {setDraft(event.target.value); setAnnouncement(""); setError("");}} placeholder={replyTo ? "Add to the conversation…" : "What do you see? Add a question or some context…"} maxLength={2000} rows={3} aria-describedby={`${composerId}-hint`} className="min-h-24 w-full resize-y rounded-sm border border-line bg-surface p-3 text-small text-ink placeholder:text-ink-muted" />
        <div className="mt-2 flex items-center justify-between gap-3"><span className="font-mono text-mono-sm tabular-nums text-ink-muted">{draft.length} / 2,000</span><button type="submit" disabled={!draft.trim()} className="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-md bg-primary px-3 text-caption font-medium text-on-primary hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-40"><Send size={13} aria-hidden="true" /> {replyTo ? 'Post reply' : 'Post comment'}</button></div>
        {error && <p role="alert" className="mt-2 text-caption text-ember">{error}</p>}
      </form>
      <p id={`${composerId}-hint`} className="mt-2 text-caption text-ink-muted">Prototype discussion · Sample conversation. New comments stay in this browser and aren’t shared with other users.</p>
    </section>}
    <p role="status" className="sr-only">{announcement}</p>
  </div>;
}
