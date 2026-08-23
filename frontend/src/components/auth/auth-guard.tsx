"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";

const PUBLIC_PATHS = ["/login", "/register"];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const isPublic = PUBLIC_PATHS.includes(pathname);
    const authed = isAuthenticated();

    if (!authed && !isPublic) {
      router.replace("/login");
      return;
    }

    if (authed && isPublic) {
      router.replace("/dashboard");
      return;
    }

    const frame = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(frame);
  }, [pathname, router]);

  if (!ready) {
    return null;
  }

  return <>{children}</>;
}
