import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * 将分页/筛选状态同步到 URL search params，返回时可恢复状态。
 * URL 更新带 debounce（默认 300ms），避免输入法中断。
 *
 * 用法：
 *   const [params, setParams] = usePageSearchParams({ page: "1", name: "" });
 *   // 读取: params.page, params.name
 *   // 修改: setParams({ page: "2" });  ← 只传要改的字段（浅合并）
 */
export function usePageSearchParams<T extends Record<string, string>>(
  defaults: T,
  delay = 300,
) {
  const [searchParams, setSearchParams] = useSearchParams();
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const defaultsRef = useRef<T>(defaults);

  // 从 URL 读取当前值
  const readFromUrl = useCallback(() => {
    const params = { ...defaultsRef.current } as T;
    for (const key of Object.keys(defaultsRef.current)) {
      const v = searchParams.get(key);
      if (v !== null) (params as Record<string, string>)[key] = v;
    }
    return params;
  }, [searchParams]);

  const [params, setLocalParams] = useState<T>(readFromUrl);

  // URL 外部变化时（如浏览器前进/后退）重新同步到本地状态
  useEffect(() => {
    setLocalParams(readFromUrl());
  }, [searchParams, readFromUrl]);

  const setParams = useCallback(
    (patch: Partial<T>) => {
      setLocalParams((prev) => {
        const next = { ...prev, ...patch };
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
          setSearchParams(
            (prevSp) => {
              const sp = new URLSearchParams(prevSp);
              for (const [k, v] of Object.entries(next)) {
                if (v === undefined || v === "" || v === defaultsRef.current[k]) {
                  sp.delete(k);
                } else {
                  sp.set(k, String(v));
                }
              }
              return sp;
            },
            { replace: true },
          );
        }, delay);
        return next;
      });
    },
    [setSearchParams, delay],
  );

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return [params, setParams] as const;
}
