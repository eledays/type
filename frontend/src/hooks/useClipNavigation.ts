import { useEffect, useCallback, useRef } from "react";
import type { ClipNavigationOptions } from "../types/options";

export function useClipNavigation({
  onNext,
  onPrevious,
  disabled = false,
  swipeThreshold = 100,
}: ClipNavigationOptions) {
  const startTouchY = useRef(0);
  const isScrolling = useRef(false);
  const hasSwiped = useRef(false);

  // Touch start handler
  const handleTouchStart = useCallback(
    (e: TouchEvent) => {
      if (disabled) return;
      startTouchY.current = e.touches[0].clientY;
      isScrolling.current = false;
    },
    [disabled]
  );

  // Touch move handler
  const handleTouchMove = useCallback(
    (e: TouchEvent) => {
      if (disabled) return;
      const currentY = e.touches[0].clientY;
      const deltaY = currentY - startTouchY.current;

      if (!isScrolling.current) {
        if (Math.abs(deltaY) > swipeThreshold) {
          isScrolling.current = true;
        }
      }

      if (isScrolling.current) {
        if (!hasSwiped.current) {
            isScrolling.current = false;
            hasSwiped.current = true;
          if (deltaY > 0) {
            onPrevious();
          } else if (deltaY < 0) {
            onNext();
          }
        }
        startTouchY.current = currentY;
      }
    },
    [disabled, onNext, onPrevious, swipeThreshold]
  );

  // Touch end handler
  const handleTouchEnd = useCallback(() => {
    if (disabled) return;
    isScrolling.current = false;
    hasSwiped.current = false;
  }, [disabled]);

  useEffect(() => {
    window.addEventListener("touchstart", handleTouchStart);
    window.addEventListener("touchmove", handleTouchMove);
    window.addEventListener("touchend", handleTouchEnd);

    return () => {
      window.removeEventListener("touchstart", handleTouchStart);
      window.removeEventListener("touchmove", handleTouchMove);
      window.removeEventListener("touchend", handleTouchEnd);
    };
  }, [handleTouchStart, handleTouchMove, handleTouchEnd]);
}
