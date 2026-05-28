import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function extractErrorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => d?.msg).filter(Boolean);
    if (msgs.length) return msgs.join(", ");
  }
  return error?.message || "Something went wrong. Please try again.";
}

function PasswordInput({ id, placeholder, value, onChange }) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <Input
        id={id}
        type={show ? "text" : "password"}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        className="pr-10"
      />
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
        tabIndex={-1}
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

export default function AuthOptionsPage() {
  const navigate = useNavigate();
  const { accessToken, isHydrated, setToken } = useAuth();

  const [mode, setMode] = useState("signin");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [signinData, setSigninData] = useState({ phone_number: "", password: "" });

  const [signupStep, setSignupStep] = useState(1);
  const [signupData, setSignupData] = useState({
    full_name: "",
    phone_number: "",
    otp_code: "",
    setup_token: "",
    password: "",
    confirm_password: "",
  });
  const [debugOtp, setDebugOtp] = useState(null);

  const [forgotStep, setForgotStep] = useState(1);
  const [forgotData, setForgotData] = useState({
    phone_number: "",
    otp_code: "",
    reset_token: "",
    new_password: "",
    confirm_password: "",
  });
  const [forgotDebugOtp, setForgotDebugOtp] = useState(null);

  useEffect(() => {
    if (isHydrated && accessToken) {
      navigate("/main-page", { replace: true });
    }
  }, [accessToken, isHydrated, navigate]);

  const canSubmitSignIn = useMemo(
    () => signinData.phone_number.trim().length >= 9 && signinData.password.length >= 8,
    [signinData]
  );

  const canSubmitRequestOtp = useMemo(
    () => signupData.full_name.trim().length >= 2 && signupData.phone_number.trim().length >= 9,
    [signupData]
  );

  const canSubmitVerifyOtp = useMemo(() => signupData.otp_code.trim().length >= 4, [signupData]);

  const canSubmitSetPassword = useMemo(
    () =>
      signupData.password.length >= 8 &&
      signupData.confirm_password.length >= 8 &&
      signupData.password === signupData.confirm_password,
    [signupData]
  );

  function switchMode(next) {
    setMode(next);
    setError("");
    setSuccess("");
  }

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
      navigate(data?.user?.onboarding_completed ? "/main-page" : "/onboarding/location");
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
      navigate("/onboarding/location");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  function resetSignupFlow() {
    setSignupStep(1);
    setDebugOtp(null);
    setSignupData({ full_name: "", phone_number: "", otp_code: "", setup_token: "", password: "", confirm_password: "" });
    setError("");
    setSuccess("");
  }

  async function handleForgotRequestOtp() {
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/forgot-password", {
        phone_number: forgotData.phone_number,
      });
      setForgotDebugOtp(data.debug_otp || null);
      setForgotStep(2);
      setSuccess(
        data.debug_otp
          ? `OTP sent. Debug OTP: ${data.debug_otp}`
          : "OTP sent to your phone number."
      );
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleForgotVerifyOtp() {
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/forgot-password/verify", {
        phone_number: forgotData.phone_number,
        otp_code: forgotData.otp_code,
      });
      setForgotData((prev) => ({ ...prev, reset_token: data.setup_token }));
      setForgotStep(3);
      setSuccess("OTP verified. Set your new password.");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleResetPassword() {
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      await api.post("/api/auth/reset-password", {
        phone_number: forgotData.phone_number,
        reset_token: forgotData.reset_token,
        new_password: forgotData.new_password,
        confirm_password: forgotData.confirm_password,
      });
      setSuccess("Password reset successfully. You can now sign in.");
      setTimeout(() => {
        setForgotStep(1);
        setForgotData({ phone_number: "", otp_code: "", reset_token: "", new_password: "", confirm_password: "" });
        setForgotDebugOtp(null);
        switchMode("signin");
      }, 1500);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-background px-4 py-10 sm:px-6 sm:py-14">
      <div className="mx-auto w-full max-w-md">
        <Card>
          <CardHeader>
            <CardTitle className="text-xl sm:text-2xl">Farmly Authentication</CardTitle>
          </CardHeader>
          <CardContent>
            {mode !== "forgot" && (
              <div className="mb-6 grid grid-cols-2 gap-2 rounded-[var(--radius)] border border-border p-1">
                <Button
                  variant={mode === "signin" ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => switchMode("signin")}
                >
                  Sign In
                </Button>
                <Button
                  variant={mode === "signup" ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => switchMode("signup")}
                >
                  Sign Up
                </Button>
              </div>
            )}

            {mode === "signin" && (
              <div className="space-y-4">
                <div>
                  <Label htmlFor="signin-phone">Phone Number</Label>
                  <Input
                    id="signin-phone"
                    placeholder="0911xxxxxx or 2519xxxxxxxx"
                    value={signinData.phone_number}
                    onChange={(e) => setSigninData((prev) => ({ ...prev, phone_number: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="signin-password">Password</Label>
                  <PasswordInput
                    id="signin-password"
                    placeholder="Minimum 8 characters"
                    value={signinData.password}
                    onChange={(e) => setSigninData((prev) => ({ ...prev, password: e.target.value }))}
                  />
                </div>
                <Button className="w-full" onClick={handleLogin} disabled={isLoading || !canSubmitSignIn}>
                  {isLoading ? "Signing in..." : "Sign In"}
                </Button>
                <button
                  type="button"
                  className="w-full text-center text-xs text-muted-foreground hover:text-foreground underline"
                  onClick={() => switchMode("forgot")}
                >
                  Forgot password?
                </button>
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
                        onChange={(e) => setSignupData((prev) => ({ ...prev, full_name: e.target.value }))}
                      />
                    </div>
                    <div>
                      <Label htmlFor="signup-phone">Phone Number</Label>
                      <Input
                        id="signup-phone"
                        placeholder="0911xxxxxx or 2519xxxxxxxx"
                        value={signupData.phone_number}
                        onChange={(e) => setSignupData((prev) => ({ ...prev, phone_number: e.target.value }))}
                      />
                    </div>
                    <Button className="w-full" onClick={handleRequestOtp} disabled={isLoading || !canSubmitRequestOtp}>
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
                        onChange={(e) => setSignupData((prev) => ({ ...prev, otp_code: e.target.value }))}
                      />
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <Button variant="outline" onClick={handleRequestOtp} disabled={isLoading}>
                        {isLoading ? "Sending..." : "Resend OTP"}
                      </Button>
                      <Button onClick={handleVerifyOtp} disabled={isLoading || !canSubmitVerifyOtp}>
                        {isLoading ? "Verifying..." : "Verify OTP"}
                      </Button>
                    </div>
                    {debugOtp && (
                      <p className="text-xs text-muted">
                        Debug OTP: <span className="font-semibold">{debugOtp}</span>
                      </p>
                    )}
                  </>
                )}

                {signupStep === 3 && (
                  <>
                    <div>
                      <Label htmlFor="signup-password">Password</Label>
                      <PasswordInput
                        id="signup-password"
                        placeholder="Minimum 8 characters"
                        value={signupData.password}
                        onChange={(e) => setSignupData((prev) => ({ ...prev, password: e.target.value }))}
                      />
                    </div>
                    <div>
                      <Label htmlFor="signup-confirm-password">Confirm Password</Label>
                      <PasswordInput
                        id="signup-confirm-password"
                        placeholder="Re-enter your password"
                        value={signupData.confirm_password}
                        onChange={(e) => setSignupData((prev) => ({ ...prev, confirm_password: e.target.value }))}
                      />
                    </div>
                    {signupData.password && signupData.confirm_password && signupData.password !== signupData.confirm_password && (
                      <p className="text-xs text-red-600">Passwords do not match.</p>
                    )}
                    <Button className="w-full" onClick={handleSetPassword} disabled={isLoading || !canSubmitSetPassword}>
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

            {mode === "forgot" && (
              <div className="space-y-4">
                <div className="mb-2">
                  <h2 className="text-base font-semibold">Reset Password</h2>
                  <p className="text-xs text-muted-foreground mt-1">
                    {forgotStep === 1 && "Enter your registered phone number to receive a reset code."}
                    {forgotStep === 2 && "Enter the OTP code sent to your phone."}
                    {forgotStep === 3 && "Set your new password."}
                  </p>
                </div>

                {forgotStep === 1 && (
                  <>
                    <div>
                      <Label htmlFor="forgot-phone">Phone Number</Label>
                      <Input
                        id="forgot-phone"
                        placeholder="0911xxxxxx or 2519xxxxxxxx"
                        value={forgotData.phone_number}
                        onChange={(e) => setForgotData((prev) => ({ ...prev, phone_number: e.target.value }))}
                      />
                    </div>
                    <Button
                      className="w-full"
                      onClick={handleForgotRequestOtp}
                      disabled={isLoading || forgotData.phone_number.trim().length < 9}
                    >
                      {isLoading ? "Sending..." : "Send Reset Code"}
                    </Button>
                  </>
                )}

                {forgotStep === 2 && (
                  <>
                    <div>
                      <Label htmlFor="forgot-otp">OTP Code</Label>
                      <Input
                        id="forgot-otp"
                        placeholder="Enter OTP code"
                        value={forgotData.otp_code}
                        onChange={(e) => setForgotData((prev) => ({ ...prev, otp_code: e.target.value }))}
                      />
                    </div>
                    {forgotDebugOtp && (
                      <p className="text-xs text-muted">
                        Debug OTP: <span className="font-semibold">{forgotDebugOtp}</span>
                      </p>
                    )}
                    <div className="grid grid-cols-2 gap-2">
                      <Button variant="outline" onClick={handleForgotRequestOtp} disabled={isLoading}>
                        Resend
                      </Button>
                      <Button
                        onClick={handleForgotVerifyOtp}
                        disabled={isLoading || forgotData.otp_code.trim().length < 4}
                      >
                        {isLoading ? "Verifying..." : "Verify"}
                      </Button>
                    </div>
                  </>
                )}

                {forgotStep === 3 && (
                  <>
                    <div>
                      <Label htmlFor="forgot-new-password">New Password</Label>
                      <PasswordInput
                        id="forgot-new-password"
                        placeholder="Minimum 8 characters"
                        value={forgotData.new_password}
                        onChange={(e) => setForgotData((prev) => ({ ...prev, new_password: e.target.value }))}
                      />
                    </div>
                    <div>
                      <Label htmlFor="forgot-confirm-password">Confirm New Password</Label>
                      <PasswordInput
                        id="forgot-confirm-password"
                        placeholder="Re-enter new password"
                        value={forgotData.confirm_password}
                        onChange={(e) => setForgotData((prev) => ({ ...prev, confirm_password: e.target.value }))}
                      />
                    </div>
                    {forgotData.new_password && forgotData.confirm_password && forgotData.new_password !== forgotData.confirm_password && (
                      <p className="text-xs text-red-600">Passwords do not match.</p>
                    )}
                    <Button
                      className="w-full"
                      onClick={handleResetPassword}
                      disabled={
                        isLoading ||
                        forgotData.new_password.length < 8 ||
                        forgotData.new_password !== forgotData.confirm_password
                      }
                    >
                      {isLoading ? "Resetting..." : "Reset Password"}
                    </Button>
                  </>
                )}

                <button
                  type="button"
                  className="w-full text-center text-xs text-muted-foreground hover:text-foreground underline"
                  onClick={() => {
                    setForgotStep(1);
                    setForgotData({ phone_number: "", otp_code: "", reset_token: "", new_password: "", confirm_password: "" });
                    setForgotDebugOtp(null);
                    switchMode("signin");
                  }}
                >
                  Back to Sign In
                </button>
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
