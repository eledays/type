import WordCont from '../WordCont/WordCont'
import styles from './Clip.module.css'
import type { ClipProps } from '../../types/components'

export default function Clip({ word, index, style }: ClipProps) {
  return (
    <>
      <div className={styles.clip} style={style}>
        <WordCont word={word} index={index} />
      </div>
    </>
  )
}