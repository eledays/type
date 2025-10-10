import { useMemo } from 'react'
import { useIsMobile } from '../../hooks/useIsMobile'

import Clip from '../Clip/Clip'
import styles from './ClipsContainer.module.css'
import type { Word } from '../../types/word'

const mockData: Word[] = [
  {
    id: 1,
    text: 'првет',
    missingIndex: 2,
    options: ['и', 'е'],
    backgroundMedia: {
      type: 'image',
      url: 'https://type.eleday.ru/get_background',
    }
  },
  {
    id: 2,
    text: 'иждвенец',
    missingIndex: 3,
    options: ['и', 'е'],
    backgroundMedia: {
      type: 'image',
      url: 'https://type.eleday.ru/get_background',
    }
  },
  {
    id: 3,
    text: 'прхождение',
    missingIndex: 2,
    options: ['и', 'е'],
    backgroundMedia: {
      type: 'image',
      url: 'https://type.eleday.ru/get_background',
    }
  }
]

export default function ClipContainer() {
  const isMobile = useIsMobile();

  const containerClass = `${styles.clipsContainer} ${isMobile ? styles.mobile : styles.desktop}`;
  const clipStyle = useMemo(() => ({
    borderRadius: isMobile ? 0 : '20px',
    width: isMobile ? '100vw' : undefined,
    aspectRatio: isMobile ? undefined : '9 / 16',
  }), [isMobile]);

  return (
    <div className={containerClass}>
      <Clip word={mockData[0]} style={{ ...clipStyle, transform: 'translateY(-100vh)' }} />
      <Clip word={mockData[1]} style={{ ...clipStyle, transform: 'translateY(0)' }} />
      <Clip word={mockData[2]} style={{ ...clipStyle, transform: 'translateY(100vh)' }} />
    </div>
  )
}