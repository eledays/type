export interface ClipNavigationOptions {
  onNext: () => void;
  onPrevious: () => void;
  disabled?: boolean;
  swipeThreshold?: number;
}