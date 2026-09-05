import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export interface MyProfile {
  id: number;
  email: string;
  category_rules: { categories?: string[] };
}

export function useMyProfile() {
  return useQuery({
    queryKey: ["my-profile"],
    queryFn: () => api.get<MyProfile>("/me"),
  });
}
