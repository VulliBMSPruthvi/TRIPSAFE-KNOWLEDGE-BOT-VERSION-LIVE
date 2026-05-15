import { Logo } from "@/components/Logo";
import { api } from "@/api/client";

export function LoginPage() {
  const onGoogle = () => {
    window.location.href = api.loginUrl();
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center px-4 relative overflow-hidden bg-gradient-to-br from-gray-50 via-white to-gray-100">
      {/* Soft animated mesh blobs */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden>
        <div className="mesh-blob mesh-blob-1" />
        <div className="mesh-blob mesh-blob-2" />
        <div className="mesh-blob mesh-blob-3" />
      </div>

      <div className="relative z-10 w-full max-w-md bg-white/80 backdrop-blur-xl rounded-2xl shadow-xl border border-white/60 p-10 sm:p-12">
        <div className="flex flex-col items-center text-center">
          <Logo variant="full" className="h-20 w-auto mb-8" />
          <h1 className="text-3xl sm:text-4xl font-semibold text-gray-900 leading-tight">
            TripSafe Knowledge Bot
          </h1>
          <p className="text-sm sm:text-base text-gray-500 mt-4 leading-relaxed max-w-sm">
            Your internal assistant for TripSafe travel insurance. Sign in with your work
            Google account to continue.
          </p>

          <button
            onClick={onGoogle}
            className="mt-10 w-full h-12 rounded-lg bg-brand-blue text-white font-medium flex items-center justify-center gap-3 shadow-btn hover:bg-brand-navy transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue"
          >
            <span className="h-7 w-7 bg-white rounded-md flex items-center justify-center shrink-0">
              <GoogleIcon />
            </span>
            <span>Sign in with Google</span>
          </button>

          <p className="text-xs text-gray-400 mt-6">
            Only authorized TripSafe / Tripjack users can access this tool.
          </p>
        </div>
      </div>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
      <path
        d="M21.6 12.227c0-.673-.06-1.32-.173-1.943H12v3.676h5.387a4.6 4.6 0 0 1-1.997 3.02v2.508h3.234c1.892-1.74 2.976-4.305 2.976-7.26z"
        fill="#4285F4"
      />
      <path
        d="M12 22c2.7 0 4.964-.895 6.62-2.422l-3.234-2.509c-.895.6-2.04.956-3.386.956-2.605 0-4.81-1.76-5.598-4.123H3.062v2.585A9.997 9.997 0 0 0 12 22z"
        fill="#34A853"
      />
      <path
        d="M6.402 13.902a5.99 5.99 0 0 1 0-3.804V7.513H3.062a10.014 10.014 0 0 0 0 8.974l3.34-2.585z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.977c1.47 0 2.787.504 3.823 1.494l2.866-2.866C16.96 3.064 14.696 2 12 2 8.087 2 4.713 4.244 3.062 7.513l3.34 2.585C7.19 7.737 9.395 5.977 12 5.977z"
        fill="#EA4335"
      />
    </svg>
  );
}
