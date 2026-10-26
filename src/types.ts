export type Option = { value: string; label: string; hint?: string };
export type MatrixItem = { id: string; label: string };

export type SurveyQuestion = {
  id: string;
  type: "single" | "multiple" | "short_text" | "long_text" | "scale" | "matrix";
  label: string;
  description?: string;
  required?: boolean;
  sensitive?: boolean;
  options?: Option[];
  min?: number;
  max?: number;
  minLabel?: string;
  maxLabel?: string;
  maxLength?: number;
  items?: MatrixItem[];
};

export type SurveyDefinition = {
  id: string;
  title: string;
  description?: string;
  version: number;
  questions: SurveyQuestion[];
};

export type MatrixAnswer = Record<string, number>;
export type Answers = Record<string, string | string[] | number | boolean | MatrixAnswer | undefined>;
