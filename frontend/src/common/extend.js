import {
  extendMethod,
  overrideMethod,
  resetExtensionPatches,
} from './extensionRuntime.js'

export function extend(target, methods, callback, options = {}) {
  return extendMethod(target, methods, callback, options)
}

export function override(target, methods, callback, options = {}) {
  return overrideMethod(target, methods, callback, options)
}

export function resetPatches(extensionId = '') {
  resetExtensionPatches(extensionId)
}

export default extend
