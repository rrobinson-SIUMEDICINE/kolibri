import findKey from 'lodash/findKey';
import { createTranslator } from 'kolibri.utils.i18n';
import bytesForHumans from 'kolibri.utils.bytesForHumans';
import logger from 'kolibri.lib.logging';

const logging = logger.getLogger(__filename);

// Strings are the _READABLE strings in le_utils.constants.format_presets,
// with ' ({fileSize})' appended.
// NOTE: Strings for 'Exercise Image', 'Exercise Graphie', and 'Channel Thumbnail'
// are excluded, as they are not downloadable in Kolibri.
const filePresetStrings = {
  highResolutionVideo: 'High Resolution ({fileSize})',
  lowResolutionVideo: 'Low Resolution ({fileSize})',
  vectorizedVideo: 'Vectorized ({fileSize})',
  // Same 'thumbnail' string is used for video, audio, document, exercise, and topic
  thumbnail: 'Thumbnail ({fileSize})',
  videoSubtitle: 'Subtitles - {langCode} ({fileSize})',
  audio: 'Audio ({fileSize})',
  document: 'Document ({fileSize})',
  exercise: 'Exercise ({fileSize})',
  html5Zip: 'HTML5 Zip ({fileSize})',
  html5Thumbnail: 'HTML5 Thumbnail ({fileSize})',
  epub: 'ePub Document ({fileSize})',
  slideshow: 'Slideshow ({fileSize})',
};

const filePresetTranslator = createTranslator('FilePresetStrings', filePresetStrings);

// 'file.preset' is an enum equal to the values in the filePresetStrings map, so this function
// searches on the values in filePresetStrings, then uses the matching key on filePreset
// translator to return the localized string.
export function getFilePresetString(file) {
  const { preset, file_size } = file;
  if (preset === 'Subtitle') {
    return filePresetTranslator.$tr('videoSubtitle', {
      langCode: file.lang.lang_code,
      fileSize: bytesForHumans(file_size),
    });
  }
  const trKey = findKey(filePresetStrings, x => x.startsWith(preset));
  if (trKey) {
    return filePresetTranslator.$tr(trKey, { fileSize: bytesForHumans(file_size) });
  }
  logging.error(`Download translation string not defined for '${preset}'`);
  return preset;
}
