import { useState, useEffect } from 'react'

function getIsMobile() {
  return typeof window !== 'undefined' && window.innerWidth <= window.innerHeight;
}

export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(getIsMobile());

  useEffect(() => {
    const handleResize = () => setIsMobile(getIsMobile());
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return isMobile;
}