import { apiJson } from "./client";

export interface HouseholdSettings {
  id: string;
  correggi_orientamento: boolean;
}

export function getHouseholdSettings(): Promise<HouseholdSettings> {
  return apiJson("/households/me/settings");
}

export function updateHouseholdSettings(correggi_orientamento: boolean): Promise<HouseholdSettings> {
  return apiJson("/households/me/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ correggi_orientamento }),
  });
}
