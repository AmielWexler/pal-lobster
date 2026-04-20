import { createPublicOauthClient } from "@osdk/oauth";

export const FOUNDRY_URL = "https://accenture.palantirfoundry.com";
export const APPLICATION_RID =
  "ri.third-party-applications.main.application.2409e8b8-feb9-4107-97ff-ba9244963033";
export const CLIENT_ID = "f70ee0f0dcdc17bef7d64a27efef6188";

// Redirect back to wherever the app is hosted (works for both localhost and production).
const REDIRECT_URI = window.location.origin;

export const auth = createPublicOauthClient(CLIENT_ID, FOUNDRY_URL, REDIRECT_URI);
