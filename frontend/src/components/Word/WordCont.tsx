import MissingLetter from '../MissingLetter/MissingLetter'

export default function WordCont(word: string, index: number) {
  return <>
    <div>
      {word = word.slice(0, index) + <MissingLetter /> + word.slice(index + 1)}
    </div>
  </>
}