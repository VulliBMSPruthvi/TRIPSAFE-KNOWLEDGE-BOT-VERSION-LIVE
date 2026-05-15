import { useEffect, useState } from "react";
import {
  api,
  type ChatModelSettings,
  type GoogleOAuthSettings,
} from "@/api/client";
import { Card, CardHeader } from "@/components/Card";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Badge } from "@/components/Badge";

export function IntegrationsPage() {
  const [model, setModel] = useState<ChatModelSettings | null>(null);
  const [oauth, setOauth] = useState<GoogleOAuthSettings | null>(null);
  const [modelSel, setModelSel] = useState<string>("");
  const [savingModel, setSavingModel] = useState(false);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [savingOauth, setSavingOauth] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const [m, g] = await Promise.all([api.getModelSettings(), api.getGoogleOAuth()]);
      setModel(m);
      setOauth(g);
      setModelSel(m.current_model);
      setClientId(g.client_id);
    })();
  }, []);

  const saveModel = async () => {
    setSavingModel(true);
    setErr(null);
    try {
      const updated = await api.setModel(modelSel);
      setModel(updated);
    } catch (e) {
      setErr(String(e));
    } finally {
      setSavingModel(false);
    }
  };

  const saveOauth = async () => {
    if (!clientId || !clientSecret) {
      setErr("Both client ID and secret are required.");
      return;
    }
    setSavingOauth(true);
    setErr(null);
    try {
      const updated = await api.setGoogleOAuth(clientId, clientSecret);
      setOauth(updated);
      setClientSecret("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setSavingOauth(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900">Integrations</h1>
        <p className="text-sm text-gray-500 mt-1">
          Switch the AI model and manage external credentials.
        </p>
      </div>

      {err && <Card className="border-danger/30"><p className="text-danger text-sm">{err}</p></Card>}

      <Card>
        <CardHeader
          title="Chat model"
          description="Active model is read from the database on every chat call — switching here takes effect immediately."
        />
        {!model ? null : (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-700">Currently active:</span>
              <Badge tone="brand">{model.current_model}</Badge>
            </div>
            <div className="grid gap-2">
              {model.available_models.map((m) => (
                <label
                  key={m.value}
                  className={`flex items-start gap-3 p-3 border rounded-md cursor-pointer transition ${
                    modelSel === m.value
                      ? "border-brand-blue bg-brand-blue/5"
                      : "border-gray-200 hover:bg-gray-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="model"
                    value={m.value}
                    checked={modelSel === m.value}
                    onChange={() => setModelSel(m.value)}
                    className="mt-1 accent-brand-blue"
                  />
                  <div>
                    <div className="text-sm font-medium text-gray-900">{m.label}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{m.description}</div>
                  </div>
                </label>
              ))}
            </div>
            <div className="flex justify-end">
              <Button
                onClick={() => void saveModel()}
                loading={savingModel}
                disabled={modelSel === model.current_model}
              >
                Apply model
              </Button>
            </div>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Google OAuth"
          description="OAuth client credentials used for Sign-in with Google. Updating these takes effect on the next login attempt."
        />
        {!oauth ? null : (
          <div className="space-y-3 max-w-2xl">
            <Input
              label="Client ID"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="123456789-xxx.apps.googleusercontent.com"
            />
            <Input
              label="Client secret"
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              type="password"
              placeholder={oauth.client_secret_set ? "•••••••••• (already set — leave blank to keep)" : "Paste new client secret"}
              hint={oauth.client_secret_set ? "Secret is stored hashed; never logged." : undefined}
            />
            <Input
              label="Redirect URI (configured in Google Cloud Console)"
              value={oauth.redirect_uri}
              readOnly
              disabled
              hint="To change, update GOOGLE_OAUTH_REDIRECT_URI env var and the Authorized redirect URI in Google Cloud Console."
            />
            <div className="flex justify-end">
              <Button
                onClick={() => void saveOauth()}
                loading={savingOauth}
                disabled={!clientId || (!clientSecret && !oauth.client_id)}
              >
                Save credentials
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
