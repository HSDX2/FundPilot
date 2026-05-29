import { useQuery } from "@tanstack/react-query";
import type { ApiEnvelope, PaginatedData } from "@/api/client";

export function usePaginatedQuery<T>(
  key: string[],
  fetcher: () => Promise<ApiEnvelope<PaginatedData<T>>>,
) {
  return useQuery({
    queryKey: key,
    queryFn: async () => {
      const res = await fetcher();
      if (!res.success) throw new Error(res.message || "Request failed");
      return res.data;
    },
  });
}
