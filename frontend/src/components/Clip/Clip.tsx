import WordCont from '../WordContainer/WordContainer'
import styles from './Clip.module.css'
import type { ClipProps } from '../../types/components'

export default function Clip({ word, index, style }: ClipProps) {
  return (
    <>
      <div className={styles.clip} style={style}>
        <div className={styles.wordContainer}>
          <WordCont word={word} index={index} />
        </div>
        <div className={styles.answersContainer}>
          {/* Answers would go here */}
        </div>
      </div>
    </>
  )
}