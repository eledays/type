import WordCont from '../WordContainer/WordContainer'
import AnswerContainer from '../AnswerContainer/AnswerContainer'
import styles from './Clip.module.css'
import type { ClipProps } from '../../types/components'

export default function Clip({ word, style }: ClipProps) {
  function renderBackgroundMedia() {
    if (!word.backgroundMedia) return null;

    if (word.backgroundMedia.type === 'image') {
      return <img src={word.backgroundMedia.url} alt="Background" className={styles.backgroundMedia} />;
    } 
    else if (word.backgroundMedia.type === 'video') {
      return (
        <video className={styles.backgroundMedia} autoPlay loop muted>
          <source src={word.backgroundMedia.url} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      );
    }
    return null;
  }

  return (
    <>
      <div className={styles.clip} style={style}>
        <div className={styles.wordContainer}>
          <WordCont word={word} />
        </div>
        <div className={styles.answersContainer}>
          <div className={styles.answerWrapper}>
            {word.options.map((option, index) => (
              <AnswerContainer content={option} key={index} />
            ))}
          </div>
        </div>
        {renderBackgroundMedia()}
      </div>
    </>
  )
}