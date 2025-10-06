// Component props interfaces

import type {Word} from './word';

export interface WordContProps {
  word: Word;
}

export interface ClipProps {
  word: Word;
  style?: React.CSSProperties;
}

export interface AnswerContainerProps {
  content: string;
}
