""" Handlers for a container dependency chain model.

Here we're interesting in storing two thing:

- What rpms are installed in a given container.
- What container images depend on what other container images.

The MetaXOR project (and lb) duplicate some of this work.  Ideally, we would
both produce caches of the authoritative information stored in koji and OSBS,
but we could write an audit script to compare and alert if there's a
difference.

"""

import logging

import pdcupdater.handlers
import pdcupdater.services
import pdcupdater.utils

from pdcupdater.handlers.depchain.base import BaseKojiDepChainHandler


log = logging.getLogger(__name__)


class ContainerRPMInclusionDepChainHandler(BaseKojiDepChainHandler):
    """ When a container build gets tagged, update PDC with rpm info. """

    # A list of the types of relationships this thing manages.
    managed_types = ('ContainerIncludesRPM',)
    # The types of the parents and children in our managed relationships
    parent_type = 'container'
    child_type = 'rpm'

    def interesting_tags(self):
        return pdcupdater.utils.interesting_container_tags()

    def _yield_koji_relationships_from_tag(self, pdc, tag):

        release_id, release = pdcupdater.utils.tag2release(tag)
        # TODO -- this tag <-> release agreement is going to break down with modularity.

        pdcupdater.utils.ensure_release_exists(pdc, release_id, release)

        builds = pdcupdater.services.koji_builds_in_tag(self.koji_url, tag)

        for i, build in enumerate(builds):
            log.info("Considering container build idx=%r, (%i of %i)" % (
                build['build_id'], i, len(builds)))

            relationships = list(self._yield_koji_relationships_from_build(
                self.koji_url, build['build_id']))

            for parent_name, relationship_type, child_name in relationships:
                parent = {
                    'name': parent_name,
                    'release': release_id,
                    #'global_component': build['srpm_name'],  # ideally.
                }
                child = {
                    'name': child_name,
                    'release': release_id,
                }
                yield parent, relationship_type, child

    def _yield_koji_relationships_from_build(self, koji_url, build_id, rpms=None):

        build = pdcupdater.services.koji_get_build(koji_url, build_id)
        parent = build['name']

        artifacts = pdcupdater.services.koji_archives_from_build(
            koji_url, build_id)

        for artifact in artifacts:
            if artifact['type_name'] in ('ks', 'cfg', 'xml'):
                continue
            log.debug("Looking up installed rpms for %r" % artifact['filename'])
            rpms = pdcupdater.services.koji_rpms_from_archive(self.koji_url, artifact)
            for entry in rpms:
                child = entry['name']
                # TODO - do some checks about external repos here...
                yield parent, 'ContainerIncludesRPM', child
