"""
Détoureur / Contoureur de base — v2
======================================
Styles de pieds :
  Cylindrique · Conique · Rectangulaire · Voronoi (alvéolaire)
  Filaire (Lattice) · Organique (Loft)

Positionnement :
  Coins · Circulaire · Bords symétriques · Suivre une courbe de sketch

Algorithme de conformation :
  Chaque pied dépasse de _OVERLAP_CM dans le corps cible, puis un
  Boolean Cut (isKeepToolBodies=True) découpe le sommet exactement sur
  la surface inférieure du corps — même si elle est courbe ou inclinée.
"""

import adsk.core
import adsk.fusion
import traceback
import math

CMD_ID = 'BaseContourFeet'
CMD_NAME = 'Pieds Contour Base'
CMD_DESC = (
    'Génère des pieds adaptés au contour exact de la base d\'un objet. '
    'Styles: cylindre, cône, Voronoi, lattice, organique. '
    'Positionnement libre ou le long d\'une courbe de sketch.'
)
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidCreatePanel'

_OVERLAP_CM = 0.05   # 0.5 mm de dépassement dans le corps
_MIN_WALL   = 0.10   # 1 mm d'épaisseur de paroi minimale

_handlers = []

FOOT_STYLES = [
    ('Cylindrique',                 True),
    ('Conique (effilé vers le bas)', False),
    ('Rectangulaire',               False),
    ('Voronoi / Alvéolaire',        False),
    ('Filaire (Lattice)',           False),
    ('Organique (Loft)',            False),
]

POSITION_MODES = [
    ('Coins de la bounding box',   True),
    ('Circulaire / équidistant',   False),
    ('Bords symétriques',          False),
]


# ─────────────────────────────────────────────────────────────────────────────
# Enregistrement / suppression
# ─────────────────────────────────────────────────────────────────────────────

def start():
    app = adsk.core.Application.get()
    ui  = app.userInterface
    existing = ui.commandDefinitions.itemById(CMD_ID)
    if existing:
        existing.deleteMe()
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_DESC)
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    panel.controls.addCommand(cmd_def)
    h = _FeetCreatedHandler()
    cmd_def.commandCreated.add(h)
    _handlers.append(h)


def stop():
    app = adsk.core.Application.get()
    ui  = app.userInterface
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    ctrl = panel.controls.itemById(CMD_ID)
    if ctrl:
        ctrl.deleteMe()
    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()


# ─────────────────────────────────────────────────────────────────────────────
# Dialogue
# ─────────────────────────────────────────────────────────────────────────────

class _FeetCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd    = args.command
            inputs = cmd.commandInputs

            # Corps cible
            sel = inputs.addSelectionInput(
                'targetBody', 'Corps cible',
                'Sélectionnez l\'objet sur lequel créer les pieds')
            sel.addSelectionFilter('SolidBodies')
            sel.setSelectionLimits(1, 1)

            # Courbe de sketch (optionnel)
            path = inputs.addSelectionInput(
                'sketchPath', 'Courbe de sketch (optionnel)',
                'Les pieds seront répartis le long de cette courbe')
            path.addSelectionFilter('SketchCurves')
            path.setSelectionLimits(0, 1)

            # Nombre de pieds
            inputs.addIntegerSpinnerCommandInput('numFeet', 'Nombre de pieds', 2, 8, 1, 4)

            # Hauteur / rayon
            inputs.addValueInput('footHeight', 'Hauteur des pieds',   'cm',
                                 adsk.core.ValueInput.createByReal(3.0))
            inputs.addValueInput('footRadius', 'Rayon des pieds',     'cm',
                                 adsk.core.ValueInput.createByReal(0.8))

            # Style
            style_drop = inputs.addDropDownCommandInput(
                'footStyle', 'Style des pieds',
                adsk.core.DropDownStyles.LabeledIconDropDownStyle)
            for label, sel_flag in FOOT_STYLES:
                style_drop.listItems.add(label, sel_flag)

            # Positionnement (masqué si courbe fournie)
            pos_drop = inputs.addDropDownCommandInput(
                'positioning', 'Positionnement',
                adsk.core.DropDownStyles.LabeledIconDropDownStyle)
            for label, sel_flag in POSITION_MODES:
                pos_drop.listItems.add(label, sel_flag)

            # Retrait du bord
            inputs.addValueInput('edgeInset', 'Retrait depuis le bord', 'cm',
                                 adsk.core.ValueInput.createByReal(1.2))

            # Handlers
            h_exec = _FeetExecuteHandler()
            cmd.execute.add(h_exec)
            _handlers.append(h_exec)

            h_val = _FeetValidateHandler()
            cmd.validateInputs.add(h_val)
            _handlers.append(h_val)

        except Exception:
            adsk.core.Application.get().userInterface.messageBox(traceback.format_exc())


class _FeetValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            i = args.inputs
            args.areInputsValid = (
                i.itemById('targetBody').selectionCount == 1
                and i.itemById('footHeight').value > 0
                and i.itemById('footRadius').value > 0
                and i.itemById('edgeInset').value >= 0
            )
        except Exception:
            args.areInputsValid = False


# ─────────────────────────────────────────────────────────────────────────────
# Exécution principale
# ─────────────────────────────────────────────────────────────────────────────

class _FeetExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            app    = adsk.core.Application.get()
            ui     = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                ui.messageBox('Aucun document Fusion 360 actif.')
                return

            inputs     = args.command.commandInputs
            body       = adsk.fusion.BRepBody.cast(
                             inputs.itemById('targetBody').selection(0).entity)
            component  = body.parentComponent
            num_feet   = int(inputs.itemById('numFeet').value)
            foot_h     = inputs.itemById('footHeight').value
            foot_r     = inputs.itemById('footRadius').value
            style      = inputs.itemById('footStyle').selectedItem.name
            pos_mode   = inputs.itemById('positioning').selectedItem.name
            inset      = inputs.itemById('edgeInset').value
            path_sel   = inputs.itemById('sketchPath')

            bbox     = body.boundingBox
            bottom_z = bbox.minPoint.z
            base_z   = bottom_z - foot_h   # bottom of the feet

            # ── Positions ────────────────────────────────────────────────────
            if path_sel.selectionCount == 1:
                curve_ent = path_sel.selection(0).entity
                positions = _points_along_curve(curve_ent, num_feet)
                if not positions:
                    ui.messageBox('Impossible d\'évaluer la courbe de sketch.')
                    return
            else:
                positions = _calculate_positions(
                    pos_mode, num_feet,
                    bbox.minPoint.x, bbox.minPoint.y,
                    bbox.maxPoint.x, bbox.maxPoint.y,
                    inset,
                    (bbox.minPoint.x + bbox.maxPoint.x) / 2.0,
                    (bbox.minPoint.y + bbox.maxPoint.y) / 2.0,
                )

            # ── Plan de base (partagé pour tous les pieds simples) ───────────
            planes        = component.constructionPlanes
            base_pi       = planes.createInput()
            base_pi.setByOffset(component.xYConstructionPlane,
                                adsk.core.ValueInput.createByReal(base_z))
            base_plane    = planes.add(base_pi)
            base_plane.name = 'Plan_Base_Pieds'

            total_h = foot_h + _OVERLAP_CM   # height incl. overlap

            # ── Créer les pieds ───────────────────────────────────────────────
            created = []
            for (px, py) in positions:
                fb = _create_foot_body(
                    component, base_plane, base_z, px, py, total_h, foot_r, style)
                if fb:
                    created.append(fb)

            base_plane.isLightBulbOn = False

            if not created:
                ui.messageBox('Aucun pied n\'a pu être créé.')
                return

            # ── Découpe du sommet au contour exact du corps ──────────────────
            combine_feats = component.features.combineFeatures
            tool_col      = adsk.core.ObjectCollection.create()
            tool_col.add(body)
            trimmed = 0
            for fb in created:
                try:
                    ci = combine_feats.createInput(fb, tool_col)
                    ci.operation          = adsk.fusion.FeatureOperations.CutFeatureOperation
                    ci.isKeepToolBodies   = True
                    combine_feats.add(ci)
                    trimmed += 1
                except Exception:
                    pass

            ui.messageBox(
                '{nf} pied(s) créé(s) — {nt} découpe(s) au contour.\n'
                'Style       : {style}\n'
                'Hauteur     : {h:.2f} cm\n'
                'Rayon       : {r:.2f} cm\n'
                'Position    : {pos}'.format(
                    nf=len(created), nt=trimmed,
                    style=style, h=foot_h, r=foot_r, pos=pos_mode),
                'Pieds Contour Base')

        except Exception:
            adsk.core.Application.get().userInterface.messageBox(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch par style
# ─────────────────────────────────────────────────────────────────────────────

def _create_foot_body(component, base_plane, base_z, px, py, total_h, radius, style):
    try:
        if 'Voronoi' in style or 'Alvéol' in style:
            return _create_voronoi(component, base_plane, px, py, total_h, radius)
        if 'Filaire' in style or 'Lattice' in style:
            return _create_lattice(component, base_plane, base_z, px, py, total_h, radius)
        if 'Organique' in style or 'Loft' in style:
            return _create_organic(component, base_plane, base_z, px, py, total_h, radius)
        if 'Conique' in style:
            return _create_tapered(component, base_plane, px, py, total_h, radius)
        if 'Rect' in style:
            return _create_rectangle(component, base_plane, px, py, total_h, radius)
        return _create_cylinder(component, base_plane, px, py, total_h, radius)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Styles de base
# ─────────────────────────────────────────────────────────────────────────────

def _create_cylinder(component, base_plane, px, py, height, radius):
    sk = component.sketches.add(base_plane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(px, py, 0.0), radius)
    if sk.profiles.count == 0:
        return None
    ei = component.features.extrudeFeatures.createInput(
        sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(height))
    ex = component.features.extrudeFeatures.add(ei)
    if ex and ex.bodies.count > 0:
        b = ex.bodies.item(0)
        b.name = 'Pied ({:.2f},{:.2f})'.format(px, py)
        return b
    return None


def _create_tapered(component, base_plane, px, py, height, radius):
    sk = component.sketches.add(base_plane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(px, py, 0.0), radius)
    if sk.profiles.count == 0:
        return None
    ei = component.features.extrudeFeatures.createInput(
        sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    taper = adsk.core.ValueInput.createByString('-7 deg')
    extent = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByReal(height))
    ei.setOneSideExtent(
        extent, adsk.fusion.ExtentDirections.PositiveExtentDirection, taper)
    ex = component.features.extrudeFeatures.add(ei)
    if ex and ex.bodies.count > 0:
        b = ex.bodies.item(0)
        b.name = 'Pied_Conique ({:.2f},{:.2f})'.format(px, py)
        return b
    return None


def _create_rectangle(component, base_plane, px, py, height, radius):
    sk = component.sketches.add(base_plane)
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(px - radius, py - radius, 0.0),
        adsk.core.Point3D.create(px + radius, py + radius, 0.0))
    if sk.profiles.count == 0:
        return None
    ei = component.features.extrudeFeatures.createInput(
        sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(height))
    ex = component.features.extrudeFeatures.add(ei)
    if ex and ex.bodies.count > 0:
        b = ex.bodies.item(0)
        b.name = 'Pied_Rect ({:.2f},{:.2f})'.format(px, py)
        return b
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Voronoi / Alvéolaire
# ─────────────────────────────────────────────────────────────────────────────

def _create_voronoi(component, base_plane, px, py, height, radius):
    """
    Cylindre plein + trous hexagonaux percés depuis le bas (78 % de la hauteur).
    Le sommet solide (22 %) sera découpé au contour du corps parent.
    """
    body = _create_cylinder(component, base_plane, px, py, height, radius)
    if not body:
        return None

    cell_r   = max(radius * 0.28, 0.20)   # rayon de chaque alvéole
    hole_r   = cell_r * 0.72              # rayon du trou (laisse des parois)
    spacing  = cell_r * math.sqrt(3)      # espacement pour packing hexagonal
    cut_depth = height * 0.78

    centers = _hex_grid(px, py, radius * 0.85, spacing)
    if not centers:
        return body

    sk_holes = component.sketches.add(base_plane)
    for (hx, hy) in centers:
        _draw_hexagon(sk_holes, hx, hy, hole_r)

    if sk_holes.profiles.count == 0:
        return body

    col = adsk.core.ObjectCollection.create()
    for i in range(sk_holes.profiles.count):
        col.add(sk_holes.profiles.item(i))

    ci = component.features.extrudeFeatures.createInput(
        col, adsk.fusion.FeatureOperations.CutFeatureOperation)
    ci.setDistanceExtent(False, adsk.core.ValueInput.createByReal(cut_depth))
    component.features.extrudeFeatures.add(ci)

    body.name = 'Pied_Voronoi ({:.2f},{:.2f})'.format(px, py)
    return body


def _hex_grid(cx, cy, outer_r, spacing):
    """Points d'une grille hexagonale dense dans un cercle de rayon outer_r."""
    centers = []
    row_h = spacing * math.sqrt(3) / 2.0
    n = int(outer_r / min(spacing, row_h)) + 2
    for row in range(-n, n + 1):
        for col in range(-n, n + 1):
            x = cx + col * spacing + (row % 2) * spacing * 0.5
            y = cy + row * row_h
            if math.hypot(x - cx, y - cy) < outer_r:
                centers.append((x, y))
    return centers


def _draw_hexagon(sketch, cx, cy, r):
    """Hexagone régulier (sommet vers le haut) dans un sketch."""
    lines = sketch.sketchCurves.sketchLines
    pts   = [adsk.core.Point3D.create(
                 cx + r * math.cos(math.pi / 6 + i * math.pi / 3),
                 cy + r * math.sin(math.pi / 6 + i * math.pi / 3),
                 0.0) for i in range(6)]
    for i in range(6):
        lines.addByTwoPoints(pts[i], pts[(i + 1) % 6])


# ─────────────────────────────────────────────────────────────────────────────
# Filaire / Lattice
# ─────────────────────────────────────────────────────────────────────────────

def _create_lattice(component, base_plane, base_z, px, py, total_h, radius):
    """
    Coque cylindrique creuse + 4 entretoises diagonales torsadées internes.
    Les entretoises sont des lofts entre cercles décalés en bas et en haut,
    créant un effet de treillis hélicoïdal.
    """
    wall_t  = max(radius * 0.14, _MIN_WALL)
    strut_r = max(radius * 0.10, _MIN_WALL * 0.7)
    inner_r = radius - wall_t

    # 1 — Coque extérieure (cylindre plein)
    shell = _create_cylinder(component, base_plane, px, py, total_h, radius)
    if not shell:
        return None

    # 2 — Creuser l'intérieur
    if inner_r > strut_r:
        sk_cut = component.sketches.add(base_plane)
        sk_cut.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(px, py, 0.0), inner_r)
        if sk_cut.profiles.count > 0:
            ci = component.features.extrudeFeatures.createInput(
                sk_cut.profiles.item(0),
                adsk.fusion.FeatureOperations.CutFeatureOperation)
            ci.setDistanceExtent(False, adsk.core.ValueInput.createByReal(total_h))
            component.features.extrudeFeatures.add(ci)

    # 3 — Plan supérieur pour les lofts
    planes = component.constructionPlanes
    top_pi = planes.createInput()
    top_pi.setByOffset(base_plane, adsk.core.ValueInput.createByReal(total_h))
    top_plane = planes.add(top_pi)
    top_plane.isLightBulbOn = False

    # 4 — 4 entretoises diagonales : base i → haut i+1 (×90°)
    mid_r        = inner_r * 0.75
    strut_bodies = []
    for i in range(4):
        b_angle = i * math.pi / 2.0
        t_angle = b_angle + math.pi / 2.0
        bx, by = px + mid_r * math.cos(b_angle), py + mid_r * math.sin(b_angle)
        tx, ty = px + mid_r * math.cos(t_angle), py + mid_r * math.sin(t_angle)

        sk_b = component.sketches.add(base_plane)
        sk_b.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(bx, by, 0.0), strut_r)
        sk_t = component.sketches.add(top_plane)
        sk_t.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(tx, ty, 0.0), strut_r)

        if sk_b.profiles.count > 0 and sk_t.profiles.count > 0:
            li = component.features.loftFeatures.createInput(
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            li.loftSections.add(sk_b.profiles.item(0))
            li.loftSections.add(sk_t.profiles.item(0))
            loft = component.features.loftFeatures.add(li)
            if loft and loft.bodies.count > 0:
                strut_bodies.append(loft.bodies.item(0))

    # 5 — Fusionner entretoises avec la coque
    if strut_bodies:
        col = adsk.core.ObjectCollection.create()
        for sb in strut_bodies:
            col.add(sb)
        ci2 = component.features.combineFeatures.createInput(shell, col)
        ci2.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
        component.features.combineFeatures.add(ci2)

    shell.name = 'Pied_Lattice ({:.2f},{:.2f})'.format(px, py)
    return shell


# ─────────────────────────────────────────────────────────────────────────────
# Organique / Loft
# ─────────────────────────────────────────────────────────────────────────────

def _create_organic(component, base_plane, base_z, px, py, total_h, radius):
    """
    Loft à travers 3 profils circulaires :
      - Base  : large  (×1.15) — au sol
      - Taille: étroit (×0.62) + léger décalage organique — à 50 % de hauteur
      - Sommet: moyen  (×0.88) — au niveau du corps
    """
    planes = component.constructionPlanes

    mid_pi = planes.createInput()
    mid_pi.setByOffset(base_plane, adsk.core.ValueInput.createByReal(total_h * 0.50))
    mid_plane = planes.add(mid_pi)
    mid_plane.isLightBulbOn = False

    top_pi = planes.createInput()
    top_pi.setByOffset(base_plane, adsk.core.ValueInput.createByReal(total_h))
    top_plane = planes.add(top_pi)
    top_plane.isLightBulbOn = False

    offset_x = radius * 0.12   # décalage organique subtil

    sk_bot = component.sketches.add(base_plane)
    sk_bot.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(px, py, 0.0), radius * 1.15)

    sk_mid = component.sketches.add(mid_plane)
    sk_mid.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(px + offset_x, py, 0.0), radius * 0.62)

    sk_top = component.sketches.add(top_plane)
    sk_top.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(px, py, 0.0), radius * 0.88)

    if (sk_bot.profiles.count == 0 or
            sk_mid.profiles.count == 0 or
            sk_top.profiles.count == 0):
        return None

    li = component.features.loftFeatures.createInput(
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    li.loftSections.add(sk_bot.profiles.item(0))
    li.loftSections.add(sk_mid.profiles.item(0))
    li.loftSections.add(sk_top.profiles.item(0))
    loft = component.features.loftFeatures.add(li)

    if loft and loft.bodies.count > 0:
        b = loft.bodies.item(0)
        b.name = 'Pied_Organique ({:.2f},{:.2f})'.format(px, py)
        return b
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Positionnement
# ─────────────────────────────────────────────────────────────────────────────

def _calculate_positions(mode, n, min_x, min_y, max_x, max_y, inset, cx, cy):
    if 'Coins' in mode:
        pool = [
            (min_x + inset, min_y + inset),
            (max_x - inset, min_y + inset),
            (max_x - inset, max_y - inset),
            (min_x + inset, max_y - inset),
            ((min_x + max_x) / 2, min_y + inset),
            ((min_x + max_x) / 2, max_y - inset),
            (min_x + inset, (min_y + max_y) / 2),
            (max_x - inset, (min_y + max_y) / 2),
        ]
        return pool[:n]

    if 'Circulaire' in mode:
        rx = max(0.1, (max_x - min_x) / 2.0 - inset)
        ry = max(0.1, (max_y - min_y) / 2.0 - inset)
        return [(cx + rx * math.cos(2 * math.pi * i / n),
                 cy + ry * math.sin(2 * math.pi * i / n))
                for i in range(n)]

    # Bords symétriques
    pool = [
        (cx, min_y + inset), (max_x - inset, cy),
        (cx, max_y - inset), (min_x + inset, cy),
        (min_x + inset, min_y + inset), (max_x - inset, min_y + inset),
        (max_x - inset, max_y - inset), (min_x + inset, max_y - inset),
    ]
    return pool[:n]


# ─────────────────────────────────────────────────────────────────────────────
# Suivi de courbe de sketch
# ─────────────────────────────────────────────────────────────────────────────

def _points_along_curve(curve_entity, num_points):
    """
    Retourne num_points positions (x, y) équidistantes le long d'une
    SketchCurve (ligne, arc, spline, cercle…).
    """
    try:
        world_geom = curve_entity.worldGeometry
        evaluator  = world_geom.evaluator
        ok, t0, t1 = evaluator.getParameterExtents()
        if not ok:
            return []

        # Courbe fermée : éviter la répétition du point de départ
        ok_s, pt_s = evaluator.getPointAtParameter(t0)
        ok_e, pt_e = evaluator.getPointAtParameter(t1)
        is_closed = (ok_s and ok_e and pt_s.distanceTo(pt_e) < 1e-4)

        divisor = num_points if is_closed else max(num_points - 1, 1)
        pts = []
        for i in range(num_points):
            t    = t0 + (t1 - t0) * i / divisor
            ok2, pt = evaluator.getPointAtParameter(t)
            if ok2:
                pts.append((pt.x, pt.y))
        return pts
    except Exception:
        return []
