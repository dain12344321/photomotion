import { createServerFn } from "@tanstack/react-start";
import { I2V_MODEL } from "@/lib/photomotion/constants";

export const xaiStatus = createServerFn({ method: "GET" }).handler(async () => {
  return {
    configured: Boolean(process.env.XAI_API_KEY),
    model: I2V_MODEL,
  };
});
