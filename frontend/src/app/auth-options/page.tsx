"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AxiosError } from "axios";

function extractErrorMessage(error: unknown) {
  const axiosError = error as AxiosError<{ detail?: string }>;
  return (
    axiosError?.response?.data?.detail ||
    axiosError?.message ||
    "Something went wrong. Please try again."
  );
}

export default function AuthOptionsPage() {
  const router = useRouter();
  const { accessToken, isHydrated, setToken } = useAuth();

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [signinData, setSigninData] = useState({
    phone_number: "",
    password: "",
  });

  const [signupStep, setSignupStep] = useState(1);
  const [signupData, setSignupData] = useState({
    full_name: "",
    phone_number: "",
    otp_code: "",
    setup_token: "",
    password: "",
    confirm_password: "",
  });
  const [debugOtp, setDebugOtp] = useState<string | null>(null);

  useEffect(() => {
    if (isHydrated && accessToken) {
      router.replace("/main-page");
    }
  }, [accessToken, isHydrated, router]);

  const canSubmitSignIn = useMemo(() => {
    return signinData.phone_number.trim().length >= 9 && signinData.password.length >= 8;
  }, [signinData]);

  const canSubmitRequestOtp = useMemo(() => {
    return (
      signupData.full_name.trim().length >= 2 &&
      signupData.phone_number.trim().length >= 9
    );
  }, [signupData]);

  const canSubmitVerifyOtp = useMemo(() => {
    return signupData.otp_code.trim().length >= 4;
  }, [signupData]);

  const canSubmitSetPassword = useMemo(() => {
    return (
      signupData.password.length >= 8 &&
      signupData.confirm_password.length >= 8 &&
      signupData.password === signupData.confirm_password
    );
  }, [signupData]);

  async function handleLogin() {
    if (!canSubmitSignIn) return;
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/login", {
        phone_number: signinData.phone_number,
        password: signinData.password,
      });
      setToken(data.access_token);
      if (data?.user?.onboarding_completed) {
        router.push("/main-page");
      } else {
        router.push("/onboarding/location");
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleRequestOtp() {
    if (!canSubmitRequestOtp) return;
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/request-otp", {
        full_name: signupData.full_name,
        phone_number: signupData.phone_number,
      });
      setDebugOtp(data.debug_otp || null);
      setSignupStep(2);
      setSuccess(
        data.debug_otp
          ? `OTP sent. Debug OTP: ${data.debug_otp}`
          : "OTP sent successfully. Please check your phone."
      );
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleVerifyOtp() {
    if (!canSubmitVerifyOtp) return;
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/verify-otp", {
        phone_number: signupData.phone_number,
        otp_code: signupData.otp_code,
      });
      setSignupData((prev) => ({ ...prev, setup_token: data.setup_token }));
      setSignupStep(3);
      setSuccess("OTP verified. Set your password to complete account setup.");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSetPassword() {
    if (!canSubmitSetPassword) return;
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/set-password", {
        phone_number: signupData.phone_number,
        setup_token: signupData.setup_token,
        password: signupData.password,
      });
      setToken(data.access_token);
      router.push("/onboarding/location");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  function resetSignupFlow() {
    setSignupStep(1);
    setDebugOtp(null);
    setSignupData({
      full_name: "",
      phone_number: "",
      otp_code: "",
      setup_token: "",
      password: "",
      confirm_password: "",
    });
    setError("");
    setSuccess("");
  }

  return (
    <main className="min-h-screen bg-background px-4 py-10 sm:px-6 sm:py-14">
      <div className="mx-auto w-full max-w-md">
        <Card>
          <CardHeader>
            <CardTitle className="text-xl sm:text-2xl">Farmly Authentication</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-6 grid grid-cols-2 gap-2 rounded-[var(--radius)] border border-border p-1">
              <Button
                variant={mode === "signin" ? "primary" : "ghost"}
                size="sm"
                onClick={() => {
                  setMode("signin");
                  setError("");
                  setSuccess("");
                }}
              >
                Sign In
              </Button>
              <Button
                variant={mode === "signup" ? "primary" : "ghost"}
                size="sm"
                onClick={() => {
                  setMode("signup");
                  setError("");
                  setSuccess("");
                }}
              >
                Sign Up
              </Button>
            </div>

            {mode === "signin" && (
              <div className="space-y-4">
                <div>
                  <Label htmlFor="signin-phone">Phone Number</Label>
                  <Input
                    id="signin-phone"
                    placeholder="0911xxxxxx or 2519xxxxxxxx"
                    value={signinData.phone_number}
                    onChange={(e) =>
                      setSigninData((prev) => ({ ...prev, phone_number: e.target.value }))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="signin-password">Password</Label>
                  <Input
                    id="signin-password"
                    type="password"
                    placeholder="Minimum 8 characters"
                    value={signinData.password}
                    onChange={(e) =>
                      setSigninData((prev) => ({ ...prev, password: e.target.value }))
                    }
                  />
                </div>
                <Button
                  className="w-full"
                  onClick={handleLogin}
                  disabled={isLoading || !canSubmitSignIn}
                >
                  {isLoading ? "Signing in..." : "Sign In"}
                </Button>
              </div>
            )}

            {mode === "signup" && (
              <div className="space-y-4">
                {signupStep === 1 && (
                  <>
                    <div>
                      <Label htmlFor="signup-name">Full Name</Label>
                      <Input
                        id="signup-name"
                        placeholder="Enter your full name"
                        value={signupData.full_name}
                        onChange={(e) =>
                          setSignupData((prev) => ({ ...prev, full_name: e.target.value }))
                        }
                      />
                    </div>
                    <div>
                      <Label htmlFor="signup-phone">Phone Number</Label>
                      <Input
                        id="signup-phone"
                        placeholder="0911xxxxxx or 2519xxxxxxxx"
                        value={signupData.phone_number}
                        onChange={(e) =>
                          setSignupData((prev) => ({ ...prev, phone_number: e.target.value }))
                        }
                      />
                    </div>
                    <Button
                      className="w-full"
                      onClick={handleRequestOtp}
                      disabled={isLoading || !canSubmitRequestOtp}
                    >
                      {isLoading ? "Requesting OTP..." : "Request OTP"}
                    </Button>
                  </>
                )}

                {signupStep === 2 && (
                  <>
                    <div>
                      <Label htmlFor="signup-otp">OTP Code</Label>
                      <Input
                        id="signup-otp"
                        placeholder="Enter OTP code"
                        value={signupData.otp_code}
                        onChange={(e) =>
                          setSignupData((prev) => ({ ...prev, otp_code: e.target.value }))
                        }
                      />
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <Button
                        variant="outline"
                        onClick={handleRequestOtp}
                        disabled={isLoading}
                      >
                        {isLoading ? "Sending..." : "Resend OTP"}
                      </Button>
                      <Button
                        onClick={handleVerifyOtp}
                        disabled={isLoading || !canSubmitVerifyOtp}
                      >
                        {isLoading ? "Verifying..." : "Verify OTP"}
                      </Button>
                    </div>
                    {debugOtp && (
                      <p className="text-xs text-muted">
                        Debug OTP available: <span className="font-semibold">{debugOtp}</span>
                      </p>
                    )}
                  </>
                )}

                {signupStep === 3 && (
                  <>
                    <div>
                      <Label htmlFor="signup-password">Password</Label>
                      <Input
                        id="signup-password"
                        type="password"
                        placeholder="Minimum 8 characters"
                        value={signupData.password}
                        onChange={(e) =>
                          setSignupData((prev) => ({ ...prev, password: e.target.value }))
                        }
                      />
                    </div>
                    <div>
                      <Label htmlFor="signup-confirm-password">Confirm Password</Label>
                      <Input
                        id="signup-confirm-password"
                        type="password"
                        placeholder="Re-enter your password"
                        value={signupData.confirm_password}
                        onChange={(e) =>
                          setSignupData((prev) => ({
                            ...prev,
                            confirm_password: e.target.value,
                          }))
                        }
                      />
                    </div>
                    {signupData.password &&
                      signupData.confirm_password &&
                      signupData.password !== signupData.confirm_password && (
                        <p className="text-xs text-red-600">Passwords do not match.</p>
                      )}
                    <Button
                      className="w-full"
                      onClick={handleSetPassword}
                      disabled={isLoading || !canSubmitSetPassword}
                    >
                      {isLoading ? "Setting Password..." : "Set Password & Continue"}
                    </Button>
                  </>
                )}

                {signupStep > 1 && (
                  <Button variant="ghost" className="w-full" onClick={resetSignupFlow}>
                    Start Over
                  </Button>
                )}
              </div>
            )}

            {error && (
              <div className="mt-4 rounded-[var(--radius)] border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}
            {success && (
              <div className="mt-4 rounded-[var(--radius)] border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
                {success}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
