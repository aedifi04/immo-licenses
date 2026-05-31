"""
Détoureur / Contoureur de base
==============================
Crée des pieds dont le SOMMET épouse parfaitement le contour de la face
inférieure d'un corps sélectionné.

Algorithme :
 1. Détecter la face la plus basse du corps (bounding box minimum Z).
 2. Calculer les positions des pieds selon le style choisi.
 3. Pour chaque pied : créer un cylindre/cône/rectangle qui dépasse
    légèrement DANS le corps (overlap = 0.5 mm).
 4. Couper chaque pied avec le corps principal (Boolean Cut, isKeepToolBodies=True).
    → Le sommet de chaque pied devient exactement la surface inférieure du corps.
"""

import adsk.core
import adsk.fusion
import traceback
import math

CMD_ID = 'BaseContourFeet'
CMD_NAME = 'Pieds Contour Base'
CMD_DESC = (
    'Génère des pieds qui s\'adaptent parfaitement au contour '
    'de la base d\'un objet (cube, forme quelconque…).'
)
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidCreatePanel'

_OVERLAP_CM = 0.05  # 0.5 mm de dépassement pour garantir l'intersection

_handlers = []


# ─────────────────────────────────────────────────────────────────────────────
# Enregistrement / suppression
# ─────────────────────────────────────────────────────────────────────────────

def start():
    app = adsk.core.Application.get()
    ui = app.userInterface

    existing = ui.commandDefinitions.itemById(CMD_ID)
    if existing:
        existing.deleteMe()

    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_DESC)

    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    panel.controls.addCommand(cmd_def)

    handler = _FeetCreatedHandler()
    cmd_def.commandCreated.add(handler)
    _handlers.append(handler)


def stop():
    app = adsk.core.Application.get()
    ui = app.userInterface

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
            cmd = args.command
            inputs = cmd.commandInputs

            # Sélection du corps cible
            body_sel = inputs.addSelectionInput(
                'targetBody',
                'Corps cible',
                'Sélectionnez l\'objet sur lequel créer les pieds',
            )
            body_sel.addSelectionFilter('SolidBodies')
            body_sel.setSelectionLimits(1, 1)

            # Nombre de pieds
            inputs.addIntegerSpinnerCommandInput(
                'numFeet', 'Nombre de pieds', 2, 8, 1, 4
            )

            # Hauteur
            inputs.addValueInput(
                'footHeight',
                'Hauteur des pieds',
                'cm',
                adsk.core.ValueInput.createByReal(3.0),
            )

            # Rayon / demi-largeur
            inputs.addValueInput(
                'footRadius',
                'Rayon des pieds',
                'cm',
                adsk.core.ValueInput.createByReal(0.8),
            )

            # Style
            style_drop = inputs.addDropDownCommandInput(
                'footStyle',
                'Style des pieds',
                adsk.core.DropDownStyles.LabeledIconDropDownStyle,
            )
            for label, sel in [
                ('Cylindrique', True),
                ('Conique (effilé vers le bas)', False),
                ('Rectangulaire', False),
            ]:
                style_drop.listItems.add(label, sel)

            # Positionnement
            pos_drop = inputs.addDropDownCommandInput(
                'positioning',
                'Positionnement',
                adsk.core.DropDownStyles.LabeledIconDropDownStyle,
            )
            for label, sel in [
                ('Coins de la bounding box', True),
                ('Circulaire / équidistant', False),
                ('Bords symétriques', False),
            ]:
                pos_drop.listItems.add(label, sel)

            # Retrait du bord
            inputs.addValueInput(
                'edgeInset',
                'Retrait depuis le bord',
                'cm',
                adsk.core.ValueInput.createByReal(1.2),
            )

            # Handlers
            on_exec = _FeetExecuteHandler()
            cmd.execute.add(on_exec)
            _handlers.append(on_exec)

            on_preview = _FeetValidateHandler()
            cmd.validateInputs.add(on_preview)
            _handlers.append(on_preview)

        except Exception:
            adsk.core.Application.get().userInterface.messageBox(
                traceback.format_exc()
            )


class _FeetValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            inputs = args.inputs
            body_sel = inputs.itemById('targetBody')
            foot_h = inputs.itemById('footHeight').value
            foot_r = inputs.itemById('footRadius').value
            inset = inputs.itemById('edgeInset').value

            args.areInputsValid = (
                body_sel.selectionCount == 1
                and foot_h > 0
                and foot_r > 0
                and inset >= 0
            )
        except Exception:
            args.areInputsValid = False


# ─────────────────────────────────────────────────────────────────────────────
# Exécution
# ─────────────────────────────────────────────────────────────────────────────

class _FeetExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)

            if not design:
                ui.messageBox('Aucun document Fusion 360 actif.')
                return

            inputs = args.command.commandInputs
            body = adsk.fusion.BRepBody.cast(
                inputs.itemById('targetBody').selection(0).entity
            )
            component = body.parentComponent

            num_feet = inputs.itemById('numFeet').value
            foot_height = inputs.itemById('footHeight').value
            foot_radius = inputs.itemById('footRadius').value
            foot_style = inputs.itemById('footStyle').selectedItem.name
            positioning = inputs.itemById('positioning').selectedItem.name
            inset = inputs.itemById('edgeInset').value

            # ── Trouver le Z le plus bas du corps ───────────────────────────
            bbox = body.boundingBox
            bottom_z = bbox.minPoint.z
            min_x, min_y = bbox.minPoint.x, bbox.minPoint.y
            max_x, max_y = bbox.maxPoint.x, bbox.maxPoint.y
            cx = (min_x + max_x) / 2.0
            cy = (min_y + max_y) / 2.0

            # ── Positions des pieds ─────────────────────────────────────────
            positions = _calculate_positions(
                positioning, int(num_feet),
                min_x, min_y, max_x, max_y,
                inset, cx, cy,
            )

            if not positions:
                ui.messageBox('Impossible de calculer les positions des pieds.')
                return

            # ── Plan de construction à la base des pieds ────────────────────
            planes = component.constructionPlanes
            plane_input = planes.createInput()
            plane_input.setByOffset(
                component.xYConstructionPlane,
                adsk.core.ValueInput.createByReal(bottom_z - foot_height),
            )
            base_plane = planes.add(plane_input)
            base_plane.name = 'Plan_Pieds_Base'

            # ── Créer chaque pied ───────────────────────────────────────────
            # Les pieds s'étendent de (bottom_z - foot_height) jusqu'à
            # (bottom_z + _OVERLAP_CM) pour garantir l'intersection avec le corps.
            extrude_height = foot_height + _OVERLAP_CM
            created = []

            for (px, py) in positions:
                fb = _create_foot_body(
                    component, base_plane,
                    px, py, extrude_height, foot_radius, foot_style,
                )
                if fb:
                    created.append(fb)

            if not created:
                ui.messageBox('Aucun pied n\'a pu être créé.')
                base_plane.isLightBulbOn = False
                return

            # ── Découpe du sommet de chaque pied via le corps principal ─────
            # Le corps principal "coupe" la partie de chaque pied qui dépasse
            # dans sa géométrie → le sommet du pied suit parfaitement la
            # surface inférieure du corps.
            combine_feats = component.features.combineFeatures
            tool_col = adsk.core.ObjectCollection.create()
            tool_col.add(body)

            trimmed = 0
            for foot_body in created:
                try:
                    ci = combine_feats.createInput(foot_body, tool_col)
                    ci.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
                    ci.isKeepToolBodies = True
                    combine_feats.add(ci)
                    trimmed += 1
                except Exception:
                    # Le pied ne touche pas le corps (position hors emprise) — OK
                    pass

            # Masquer le plan de construction
            base_plane.isLightBulbOn = False

            ui.messageBox(
                '{nf} pied(s) créé(s), {nt} découpé(s) au contour exact de la base.\n\n'
                'Style       : {style}\n'
                'Hauteur     : {h:.1f} cm\n'
                'Rayon       : {r:.1f} cm\n'
                'Positionnement : {pos}'.format(
                    nf=len(created),
                    nt=trimmed,
                    style=foot_style,
                    h=foot_height,
                    r=foot_radius,
                    pos=positioning,
                ),
                'Pieds Contour Base — Plugin',
            )

        except Exception:
            adsk.core.Application.get().userInterface.messageBox(
                traceback.format_exc()
            )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _calculate_positions(mode, n, min_x, min_y, max_x, max_y, inset, cx, cy):
    """Retourne une liste de (x, y) pour chaque pied."""
    positions = []

    if 'Coins' in mode:
        corners = [
            (min_x + inset, min_y + inset),
            (max_x - inset, min_y + inset),
            (max_x - inset, max_y - inset),
            (min_x + inset, max_y - inset),
        ]
        mid_front = ((min_x + max_x) / 2.0, min_y + inset)
        mid_back  = ((min_x + max_x) / 2.0, max_y - inset)
        mid_left  = (min_x + inset, (min_y + max_y) / 2.0)
        mid_right = (max_x - inset, (min_y + max_y) / 2.0)

        extras = [mid_front, mid_back, mid_left, mid_right]

        pool = corners + extras
        positions = pool[:n]

    elif 'Circulaire' in mode:
        rx = max(0.1, (max_x - min_x) / 2.0 - inset)
        ry = max(0.1, (max_y - min_y) / 2.0 - inset)
        for i in range(n):
            angle = (2.0 * math.pi * i) / n
            positions.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))

    elif 'Bords' in mode or 'sym' in mode.lower():
        # Distribués sur le périmètre de la bounding box
        perimeter_pts = [
            (cx, min_y + inset),
            (max_x - inset, cy),
            (cx, max_y - inset),
            (min_x + inset, cy),
        ]
        pool = perimeter_pts
        # Si plus de 4 pieds, ajouter les coins
        if n > 4:
            pool += [
                (min_x + inset, min_y + inset),
                (max_x - inset, min_y + inset),
                (max_x - inset, max_y - inset),
                (min_x + inset, max_y - inset),
            ]
        positions = pool[:n]

    return positions


def _create_foot_body(component, base_plane, px, py, height, radius, style):
    """
    Crée un corps solide (cylindre, cône ou boîte) centré en (px, py)
    sur le plan base_plane, extrudé vers le haut de `height` cm.
    Retourne le BRepBody créé, ou None en cas d'erreur.
    """
    try:
        sketch = component.sketches.add(base_plane)
        curves = sketch.sketchCurves

        if 'Rect' in style:
            lines = curves.sketchLines
            lines.addTwoPointRectangle(
                adsk.core.Point3D.create(px - radius, py - radius, 0.0),
                adsk.core.Point3D.create(px + radius, py + radius, 0.0),
            )
        else:
            circles = curves.sketchCircles
            circles.addByCenterRadius(
                adsk.core.Point3D.create(px, py, 0.0), radius
            )

        if sketch.profiles.count == 0:
            return None

        profile = sketch.profiles.item(0)
        extrude_feats = component.features.extrudeFeatures

        if 'Conique' in style:
            ei = extrude_feats.createInput(
                profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            # Taper angle négatif → la base (en bas) est plus large
            taper = adsk.core.ValueInput.createByString('-7 deg')
            extent = adsk.fusion.DistanceExtentDefinition.create(
                adsk.core.ValueInput.createByReal(height)
            )
            ei.setOneSideExtent(
                extent,
                adsk.fusion.ExtentDirections.PositiveExtentDirection,
                taper,
            )
        else:
            ei = extrude_feats.createInput(
                profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            ei.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByReal(height),
            )

        extrude = extrude_feats.add(ei)

        if extrude and extrude.bodies.count > 0:
            foot_body = extrude.bodies.item(0)
            foot_body.name = 'Pied ({:.2f}, {:.2f})'.format(px, py)
            return foot_body

    except Exception:
        pass

    return None
