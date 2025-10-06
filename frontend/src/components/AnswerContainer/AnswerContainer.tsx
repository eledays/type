import type {AnswerContainerProps} from '../../types/components'
import styles from './AnswerContainer.module.css'

export default function AnswerContainer({content}: AnswerContainerProps) {
  return <span className={styles.answerContainer}>{content}</span>
}