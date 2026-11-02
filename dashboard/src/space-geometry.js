export const LIGHT_YEARS_PER_PARSEC = 3.26156;

// Heliocentric ICRS Cartesian positions, with distance in parsecs.
export function positionFromAstrometry(raDeg, decDeg, parallaxMas) {
  if (![raDeg, decDeg, parallaxMas].every(Number.isFinite) || raDeg < 0 || raDeg >= 360 || decDeg < -90 || decDeg > 90 || parallaxMas <= 0) return null;
  const ra = raDeg * Math.PI / 180;
  const dec = decDeg * Math.PI / 180;
  const distance = 1000 / parallaxMas;
  return { x: distance * Math.cos(dec) * Math.cos(ra), y: distance * Math.cos(dec) * Math.sin(ra), z: distance * Math.sin(dec), distance };
}

export function nominalDistanceLightYears(row) {
  const position = positionFromAstrometry(row?.ra_deg, row?.dec_deg, row?.parallax_mas);
  return position ? position.distance * LIGHT_YEARS_PER_PARSEC : null;
}

// Orthographic projection after rotating the actual Cartesian coordinates.
export function projectPosition(point, yaw, pitch, zoom = 1) {
  const horizontal = point.x * Math.cos(yaw) - point.y * Math.sin(yaw);
  const rotatedY = point.x * Math.sin(yaw) + point.y * Math.cos(yaw);
  const vertical = rotatedY * Math.sin(pitch) + point.z * Math.cos(pitch);
  const depth = rotatedY * Math.cos(pitch) - point.z * Math.sin(pitch);
  return { x: 400 + horizontal * 0.12 * zoom, y: 260 - vertical * 0.12 * zoom, depth };
}
