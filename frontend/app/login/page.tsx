import { Suspense } from "react";

import { LoginForm } from "@/app/login/login-form";

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="p-8 text-center">Loading sign-in…</p>}>
      <LoginForm />
    </Suspense>
  );
}
