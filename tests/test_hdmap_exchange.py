from __future__ import annotations

from app.hdmap import (
    Lane,
    LaneBoundary,
    export_lanelet2_xml,
    export_lanes_to_opendrive,
    import_lanelet2_xml,
    import_opendrive_lanes,
)


def test_opendrive_vector_lane_round_trip() -> None:
    lane = Lane(
        id="lane_1",
        centerline=[(116.0, 39.0), (116.001, 39.0)],
        left_boundary="left_1",
        right_boundary="right_1",
        speed_limit=50,
        turn_type="through",
        successor_ids=["lane_2"],
    )
    xml = export_lanes_to_opendrive([lane], [LaneBoundary("left_1", [(116.0, 39.0), (116.001, 39.0)])])
    imported = import_opendrive_lanes(xml)

    assert imported[0].id == "lane_1"
    assert imported[0].centerline == lane.centerline
    assert imported[0].successor_ids == ["lane_2"]


def test_lanelet2_import_and_export() -> None:
    xml = """
    <osm>
      <node id="1" lon="116.0" lat="39.0" />
      <node id="2" lon="116.001" lat="39.0" />
      <node id="3" lon="116.0" lat="39.0001" />
      <node id="4" lon="116.001" lat="39.0001" />
      <way id="10"><nd ref="1"/><nd ref="2"/><tag k="type" v="line_thin"/></way>
      <way id="11"><nd ref="3"/><nd ref="4"/><tag k="type" v="line_thin"/></way>
      <relation id="20">
        <member type="way" ref="10" role="left"/>
        <member type="way" ref="11" role="right"/>
        <tag k="type" v="lanelet"/>
        <tag k="speed_limit" v="45"/>
      </relation>
    </osm>
    """
    lanes, boundaries = import_lanelet2_xml(xml)
    exported = export_lanelet2_xml(lanes, boundaries)

    assert lanes[0].id == "lanelet_20"
    assert len(lanes[0].centerline) == 2
    assert len(boundaries) == 2
    assert "<relation" in exported
