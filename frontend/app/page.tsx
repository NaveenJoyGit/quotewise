import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export default function Home() {
  const cookieStore = cookies();
  const hasKey = cookieStore.has("contractor_key");
  redirect(hasKey ? "/quotes" : "/login");
}
