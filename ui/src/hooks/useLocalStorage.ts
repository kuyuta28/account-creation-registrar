import { useState, useEffect, Dispatch, SetStateAction } from "react";

/**
 * useState nhưng tự persist vào localStorage.
 * Lần đầu load: đọc từ storage (nếu có), fallback sang initialValue.
 * Mỗi khi state thay đổi: ghi lại storage.
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw !== null ? (JSON.parse(raw) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // storage full hoặc private mode — bỏ qua
    }
  }, [key, value]);

  return [value, setValue];
}
