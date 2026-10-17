import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.movieswipe.app",
  appName: "sai",
  webDir: "dist",
  backgroundColor: "#0b0b12",
  server: {
    // The backend runs on your PC over plain HTTP on the local network, so the app itself is served over http
    // too (an https page can't call an http API).
    androidScheme: "http",
    cleartext: true,
  },
  android: {
    allowMixedContent: true,
  },
};

export default config;
