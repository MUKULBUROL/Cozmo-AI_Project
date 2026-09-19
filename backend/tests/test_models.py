"""Unit tests for Pydantic core models and Output Contract."""

import unittest
from backend.app.models.output import (
    Measurement,
    DimensionedWall,
    DimensionedRoom,
    DimensionedOpening,
    PropertyPlanOutput,
    DamageRegion,
    DamageClass,
)
from backend.app.models.capture import CaptureTier
from backend.app.models.floorplan import Point2D
from backend.app.models.geometry import OpeningType


class TestModels(unittest.TestCase):
    def test_measurement_schema(self):
        m = Measurement[float](
            value=4.32,
            unit="m",
            lower_bound=4.29,
            upper_bound=4.35,
            confidence=0.95,
            method="lidar_plane_fit",
        )
        self.assertEqual(m.value, 4.32)
        self.assertEqual(m.unit, "m")
        self.assertEqual(m.lower_bound, 4.29)
        self.assertEqual(m.upper_bound, 4.35)
        self.assertEqual(m.confidence, 0.95)
        self.assertEqual(m.method, "lidar_plane_fit")

        data = m.model_dump()
        self.assertEqual(data["value"], 4.32)
        self.assertEqual(data["confidence"], 0.95)

    def test_property_plan_output_contract(self):
        wall = DimensionedWall(
            wall_id="wall_001",
            start=Point2D(x=0.0, y=0.0),
            end=Point2D(x=4.32, y=0.0),
            length=Measurement[float](
                value=4.32,
                unit="m",
                lower_bound=4.29,
                upper_bound=4.35,
                confidence=0.95,
                method="lidar_plane_fit",
            ),
            thickness=Measurement[float](
                value=0.15,
                unit="m",
                lower_bound=0.14,
                upper_bound=0.16,
                confidence=0.90,
                method="prior_standard_stud",
            ),
        )

        room = DimensionedRoom(
            room_id="room_001",
            name="Living Room",
            floor_area=Measurement[float](
                value=18.5,
                unit="m2",
                lower_bound=18.1,
                upper_bound=18.9,
                confidence=0.95,
                method="polygon_integration",
            ),
            perimeter=Measurement[float](
                value=17.2,
                unit="m",
                lower_bound=17.0,
                upper_bound=17.4,
                confidence=0.95,
                method="wall_perimeter_sum",
            ),
            ceiling_height=Measurement[float](
                value=2.45,
                unit="m",
                lower_bound=2.44,
                upper_bound=2.46,
                confidence=0.95,
                method="ceiling_floor_plane_distance",
            ),
            walls=[wall],
        )

        output = PropertyPlanOutput(
            property_id="property_001",
            capture_id="c7d28f72c6",
            tier=CaptureTier.LIDAR,
            rooms=[room],
            total_floor_area=Measurement[float](
                value=18.5,
                unit="m2",
                lower_bound=18.1,
                upper_bound=18.9,
                confidence=0.95,
                method="room_area_sum",
            ),
            reconstruction_method="ARKit_LiDAR_PlaneFit",
        )

        json_str = output.model_dump_json(indent=2)
        self.assertIn("property_001", json_str)
        self.assertIn("lidar_plane_fit", json_str)


if __name__ == "__main__":
    unittest.main()
