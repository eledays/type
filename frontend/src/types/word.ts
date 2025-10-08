// Word types

export interface Word {
  id: number;
  text: string;
  missingIndex: number;
  options: string[];
  backgroundMedia?: {
    type: 'image' | 'video';
    url: string;
  }
}
