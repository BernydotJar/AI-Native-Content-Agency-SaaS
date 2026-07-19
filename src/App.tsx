import { DemoApp } from "./control-plane/DemoApp";
import { IntegratedApp } from "./control-plane/IntegratedApp";

type RuntimeMode = "integrated" | "demo";

function resolveRuntimeMode(value: string | undefined): RuntimeMode {
  return value?.trim().toLowerCase() === "demo" ? "demo" : "integrated";
}

export default function App() {
  const mode = resolveRuntimeMode(import.meta.env.VITE_RUNTIME_MODE);
  return mode === "demo" ? <DemoApp /> : <IntegratedApp />;
}
