// 文字セット定義。文字列は codepoint 単位で扱うため、展開には [...str] を使う。

const HIRAGANA_BASIC =
  "あいうえお" +
  "かきくけこ" +
  "さしすせそ" +
  "たちつてと" +
  "なにぬねの" +
  "はひふへほ" +
  "まみむめも" +
  "やゆよ" +
  "らりるれろ" +
  "わをん";

const HIRAGANA_EXTENDED =
  "がぎぐげご" +
  "ざじずぜぞ" +
  "だぢづでど" +
  "ばびぶべぼ" +
  "ぱぴぷぺぽ" +
  "ゃゅょっ";

const KATAKANA_BASIC =
  "アイウエオ" +
  "カキクケコ" +
  "サシスセソ" +
  "タチツテト" +
  "ナニヌネノ" +
  "ハヒフヘホ" +
  "マミムメモ" +
  "ヤユヨ" +
  "ラリルレロ" +
  "ワヲン";

// 文章で頻出し、画数が極端に多くない初期漢字 (DESIGN §11.2)。
const KANJI_FREQ =
  "日本人大小中上下山川" +
  "田口目手足年月火水木" +
  "金土今何私君行見言語" +
  "書読食生学校先時間";

const DIGITS = "0123456789";

const PUNCTUATION = "。、・「」ー";

export type CharsetDef = {
  name: string;
  label: string;
  chars: string[];
};

function chars(source: string): string[] {
  return [...source];
}

export const CHARSETS: CharsetDef[] = [
  { name: "hiragana_basic", label: "ひらがな基本 (46字)", chars: chars(HIRAGANA_BASIC) },
  { name: "hiragana_extended", label: "ひらがな濁音・小書き", chars: chars(HIRAGANA_EXTENDED) },
  { name: "katakana_basic", label: "カタカナ基本 (46字)", chars: chars(KATAKANA_BASIC) },
  { name: "kanji_freq", label: "頻出漢字", chars: chars(KANJI_FREQ) },
  { name: "digits", label: "数字 (0-9)", chars: chars(DIGITS) },
  { name: "punctuation", label: "句読点・記号", chars: chars(PUNCTUATION) },
];

export function getCharset(name: string): CharsetDef {
  const found = CHARSETS.find((c) => c.name === name);
  if (!found) {
    throw new Error(`unknown charset: ${name}`);
  }
  return found;
}
