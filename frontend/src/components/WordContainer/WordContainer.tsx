import MissingLetter from '../MissingLetter/MissingLetter'
import type { WordContProps } from '../../types/components'

export default function WordCont({ word, index }: WordContProps) {
  return (
    <div>
      {word.slice(0, index)}
      <MissingLetter />
      {word.slice(index)}
    </div>
  )
}