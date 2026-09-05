import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { MyProfile } from "./useMyProfile";

export function useUpdateMyCategories() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (categories: string[]) => api.patch<MyProfile>("/me/categories", { categories }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-profile"] });
    },
  });
}
