import MissingLetter from '../MissingLetter/MissingLetter'
import type { WordContProps } from '../../types/components'
import styles from './WordContainer.module.css'

export default function WordCont({ word }: WordContProps) {
  return (
    <div className={styles.wordContainer}>
      {word.text.slice(0, word.missingIndex)}
      <MissingLetter />
      {word.text.slice(word.missingIndex)}
    </div>
  )
}