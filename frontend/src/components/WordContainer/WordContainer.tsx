import MissingLetter from '../MissingLetter/MissingLetter'
import type { WordContProps } from '../../types/components'

export default function WordCont({ word }: WordContProps) {
  return (
    <div>
      {word.text.slice(0, word.missingIndex)}
      <MissingLetter />
      {word.text.slice(word.missingIndex)}
    </div>
  )
}