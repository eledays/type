import { useState, useEffect, useMemo } from 'react'

import Clip from '../Clip/Clip'
import styles from './ClipsContainer.module.css'

function getIsMobile() {
  // Добавить проверку на существование window
  return typeof window !== 'undefined' && window.innerWidth <= window.innerHeight;
}

export default function ClipContainer() {
  // Или использовать lazy initial state:
  const [isMobile, setIsMobile] = useState(() => getIsMobile());

  useEffect(() => {
    const handleResize = () => setIsMobile(getIsMobile());
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const containerClass = `${styles.clipsContainer} ${isMobile ? styles.mobile : styles.desktop}`;
  const clipStyle = useMemo(() => ({
    borderRadius: isMobile ? 0 : '20px',
    width: isMobile ? '100vw' : undefined,
    aspectRatio: isMobile ? undefined : '9 / 16',
  }), [isMobile]);

  return (
    <div className={containerClass}>
      <Clip word="wod" index={2} style={{ ...clipStyle, transform: 'translateY(-100vh)' }} />
      <Clip word="wod" index={2} style={{ ...clipStyle, transform: 'translateY(0)' }} />
      <Clip word="wod" index={2} style={{ ...clipStyle, transform: 'translateY(100vh)' }} />
    </div>
  )
}