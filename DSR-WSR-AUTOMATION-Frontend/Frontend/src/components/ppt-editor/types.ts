export type ElementType = "text" | "image" | "shape";

export interface TextStyle {
  fontSize: number;
  fontFamily: string;
  color: string;
  bold: boolean;
  italic: boolean;
  align: "left" | "center" | "right";
}

export interface BaseElement {
  id: string;
  type: ElementType;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  locked?: boolean;
  sourceShapeId?: number;
  originalX?: number;
  originalY?: number;
  originalWidth?: number;
  originalHeight?: number;
}

export interface TextElement extends BaseElement {
  type: "text";
  text: string;
  style: TextStyle;
  tableRow?: number;
  tableCol?: number;
  /** When true, element moves with its parent table in the deck — only text is patched on export */
  positionLocked?: boolean;
  /** Text differs from last synced PPT state */
  isDirty?: boolean;
  originalText?: string;
}

export interface ImageElement extends BaseElement {
  type: "image";
  src: string;
}

export interface ShapeElement extends BaseElement {
  type: "shape";
  shapeKind: "rect";
  fill: string;
  stroke: string;
  strokeWidth: number;
  isTableCell?: boolean;
  tableRow?: number;
  tableCol?: number;
}

export type SlideElement = TextElement | ImageElement | ShapeElement;

export interface EditorSlide {
  id: string;
  index: number;
  title: string;
  background: string;
  backgroundImage: string | null;
  elements: SlideElement[];
}

export interface PresentationDocument {
  id: string;
  filename: string;
  canvasWidth: number;
  canvasHeight: number;
  slideWidthEmu?: number;
  slideHeightEmu?: number;
  sourcePptPath?: string;
  slides: EditorSlide[];
}

export const DEFAULT_TEXT_STYLE: TextStyle = {
  fontSize: 18,
  fontFamily: "Calibri, Arial, sans-serif",
  color: "#111827",
  bold: false,
  italic: false,
  align: "left",
};

export const CANVAS_WIDTH = 1280;
export const CANVAS_HEIGHT = 720;
