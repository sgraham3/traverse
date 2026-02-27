# Traverse File Format

A traverse file is a plain text file that defines a sequence of straight and curved courses.  
It is automatically created when saving a traverse, but it can also be manually authored and loaded into the Traverse tool.

---

## Sample Traverse File

```
DT QB
DU DMS
SP 454868.9 298986.09
EP 454868.9 298986.09
DD N90-0-0E 105
AD 45-0-0 100
TC C 45 D 100-0-0 L
NC C 45 D 100-0-0 C N45-0-0E R
```

---

# File Structure

A traverse file consists of:

1. **Header records**
   - Direction type
   - Direction units
   - Start point
   - Optional end point

2. **Course records**
   - Straight lines
   - Tangent curves
   - Nontangent curves

Each record begins with a keyword identifier.

---

# General Rules

- Direction values must match the declared direction type and units.
- No spaces are allowed inside direction values.
- Angles must follow the format required by the specified units.
- Distances are numeric and interpreted in the coordinate system’s linear units.

---

# Header Records

## DT — Direction Type (Required)

Defines how directions are interpreted.

Valid values:

- `QB` — Quadrant Bearing
- `NA` — North Azimuth
- `SA` — South Azimuth
- `P`  — Polar Direction

---

## DU — Direction Units (Required)

Defines angular units.

Valid values:

- `DD`  — Decimal Degrees
- `DMS` — Degrees Minutes Seconds
- `R`   — Radians
- `G`   — Gradians (Gons)

---

## SP — Start Point (Required)

```
SP <X> <Y>
```

Defines the starting coordinate of the traverse.

---

## EP — End Point (Optional)

```
EP <X> <Y>
```

Defines a closing coordinate for the traverse.

---

# Course Records

## DD — Direction–Distance (Straight Line)

```
DD <direction> <distance>
```

Defines a straight line using an absolute direction and distance.

Example:

```
DD N90-0-0E 105
```

---

## AD — Angle–Distance (Straight Line)

```
AD <angle> <distance>
```

Defines a straight line using an angle relative to the previous course.

⚠️ Cannot be used as the first course.

Example:

```
AD 45-0-0 100
```

---

# Curves

## TC — Tangent Curve

```
TC <param1> <value1> <param2> <value2> <direction>
```

Defines a curve tangent to the previous course.

### Curve Parameters

Each parameter pair consists of:

| Token | Meaning        |
|-------|---------------|
| D     | Central angle |
| A     | Arc length    |
| C     | Chord length  |
| R     | Radius        |

Two parameter/value pairs must be provided.

### Turn Direction

- `L` — Left
- `R` — Right

Example:

```
TC C 45 D 100-0-0 L
```

---

## NC — Nontangent Curve

```
NC <param1> <value1> <param2> <value2> <ref> <direction> <turn>
```

Defines a curve not tangent to the previous course.

### Required Components

1. Two curve construction parameters (same tokens as TC)
2. A reference direction type
3. A direction value
4. Turn direction

### Reference Tokens

| Token | Meaning            |
|-------|-------------------|
| C     | Chord direction   |
| R     | Radial direction  |
| T     | Tangent direction |

### Turn Direction

- `L` — Left
- `R` — Right

Example:

```
NC C 45 D 100-0-0 C N45-0-0E R
```

---

# Summary of Record Types

| Code | Description |
|------|------------|
| DT   | Direction type |
| DU   | Direction units |
| SP   | Start point |
| EP   | End point |
| DD   | Direction–distance line |
| AD   | Angle–distance line |
| TC   | Tangent curve |
| NC   | Nontangent curve |

---

# Notes

- The traverse is processed sequentially.
- Each new course begins where the previous one ends.
- Curve definitions require sufficient parameters to compute geometry.
- Direction formatting must strictly match the declared units.

---

# End of Traverse File Format Documentation