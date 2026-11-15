import { redirect } from "next/navigation";
import { currentUserId, profileHref } from "@/lib/profiles";

export default function ProfilePage() {
  redirect(profileHref(currentUserId));
}
