<template>

  <div>
    <KGrid>
      <KGridItem
        :layout8="{ span: 4 }"
        :layout12="{ span: 6 }"
      >
        <h1>{{ coreString('usersLabel') }}</h1>
      </KGridItem>
      <KGridItem
        :layout="{ alignment: 'right' }"
        :layout8="{ span: 4 }"
        :layout12="{ span: 6 }"
      >
        <KButton
          :text="$tr('newUserButtonLabel')"
          :primary="true"
          class="move-down"
          @click="displayModal(Modals.CREATE_USER)"
        />
      </KGridItem>
    </KGrid>

    <PaginatedListContainer
      :items="facilityUsers"
      :filterFunction="filterUsers"
      :filterPlaceholder="$tr('searchText')"
    >
      <template v-slot:otherFilter>
        <KSelect
          v-model="roleFilter"
          :label="coreString('userTypeLabel')"
          :options="userKinds"
          :inline="true"
          class="type-filter"
        />
      </template>

      <template v-slot:default="{items, filterInput}">
        <UserTable
          class="user-roster move-down"
          :users="items"
          :emptyMessage="emptyMessageForItems(items, filterInput)"
        >
          <template slot="action" slot-scope="userRow">
            <KDropdownMenu
              :text="$tr('optionsButtonLabel')"
              :options="manageUserOptions(userRow.user.id)"
              :disabled="!userCanBeEdited(userRow.user)"
              appearance="flat-button"
              @select="handleManageUserSelection($event, userRow.user)"
            />
          </template>
        </UserTable>
      </template>
    </PaginatedListContainer>

    <!-- Modals -->
    <UserCreateModal v-if="modalShown===Modals.CREATE_USER" @cancel="closeModal" />

    <EditUserModal
      v-if="modalShown===Modals.EDIT_USER"
      :id="selectedUser.id"
      :name="selectedUser.full_name"
      :username="selectedUser.username"
      :kind="selectedUser.kind"
      @cancel="closeModal"
    />

    <ResetUserPasswordModal
      v-if="modalShown===Modals.RESET_USER_PASSWORD"
      :id="selectedUser.id"
      :username="selectedUser.username"
      @cancel="closeModal"
    />

    <DeleteUserModal
      v-if="modalShown===Modals.DELETE_USER"
      :id="selectedUser.id"
      :username="selectedUser.username"
      @cancel="closeModal"
    />
  </div>

</template>


<script>

  import { mapActions, mapState, mapGetters } from 'vuex';
  import { UserKinds } from 'kolibri.coreVue.vuex.constants';
  import commonCoreStrings from 'kolibri.coreVue.mixins.commonCoreStrings';
  import PaginatedListContainer from 'kolibri.coreVue.components.PaginatedListContainer';
  import UserTable from '../UserTable';
  import { Modals } from '../../constants';
  import { userMatchesFilter, filterAndSortUsers } from '../../userSearchUtils';
  import UserCreateModal from './UserCreateModal';
  import EditUserModal from './EditUserModal';
  import ResetUserPasswordModal from './ResetUserPasswordModal';
  import DeleteUserModal from './DeleteUserModal';

  const ALL_FILTER = 'all';

  export default {
    name: 'UserPage',
    metaInfo() {
      return {
        title: this.coreString('usersLabel'),
      };
    },
    components: {
      UserCreateModal,
      EditUserModal,
      ResetUserPasswordModal,
      DeleteUserModal,
      UserTable,
      PaginatedListContainer,
    },
    mixins: [commonCoreStrings],
    data() {
      return {
        roleFilter: null,
        selectedUser: null,
      };
    },
    computed: {
      ...mapGetters(['currentUserId', 'isSuperuser']),
      ...mapState('userManagement', ['facilityUsers', 'modalShown']),
      Modals: () => Modals,
      userKinds() {
        return [
          { label: this.coreString('allLabel'), value: ALL_FILTER },
          { label: this.coreString('learnersLabel'), value: UserKinds.LEARNER },
          { label: this.coreString('coachesLabel'), value: UserKinds.COACH },
          { label: this.$tr('admins'), value: UserKinds.ADMIN },
        ];
      },
    },
    beforeMount() {
      this.roleFilter = this.userKinds[0];
    },
    methods: {
      ...mapActions('userManagement', ['displayModal']),
      emptyMessageForItems(items, filterText) {
        if (this.facilityUsers.length === 0) {
          return this.$tr('noUsersExist');
        } else if (items.length === 0) {
          return this.$tr('allUsersFilteredOut', { filterText });
        }
        return '';
      },
      filterUsers(users, filterText) {
        return filterAndSortUsers(
          users,
          user => userMatchesFilter(user, filterText) && this.userMatchesRole(user, this.roleFilter)
        );
      },
      closeModal() {
        this.displayModal(false);
      },
      userMatchesRole(user, roleFilter) {
        const { value: filterKind } = roleFilter;
        if (filterKind === ALL_FILTER) {
          return true;
        }
        if (user.kind === UserKinds.ASSIGNABLE_COACH) {
          return filterKind === UserKinds.COACH;
        }
        if (filterKind === UserKinds.ADMIN) {
          return user.kind === UserKinds.ADMIN || user.kind === UserKinds.SUPERUSER;
        }
        return filterKind === user.kind;
      },
      manageUserOptions(userId) {
        return [
          { label: this.coreString('editDetailsAction'), value: Modals.EDIT_USER },
          { label: this.$tr('resetUserPassword'), value: Modals.RESET_USER_PASSWORD },
          {
            label: this.coreString('deleteAction'),
            value: Modals.DELETE_USER,
            disabled: userId === this.currentUserId,
          },
        ];
      },
      handleManageUserSelection(selection, user) {
        this.selectedUser = user;
        this.displayModal(selection.value);
      },
      userCanBeEdited(user) {
        // If logged-in user is a superuser, then they can edit anybody (including other SUs).
        // Otherwise, only non-SUs can be edited.
        return this.isSuperuser || !user.is_superuser;
      },
    },
    $trs: {
      searchText: 'Search for a user…',
      admins: 'Admins',
      newUserButtonLabel: 'New User',
      noUsersExist: 'No users exist',
      allUsersFilteredOut: "No users match the filter: '{filterText}'",
      optionsButtonLabel: 'Options',
      resetUserPassword: 'Reset password',
    },
  };

</script>


<style lang="scss" scoped>

  .move-down {
    position: relative;
    margin-top: 24px;
  }

  .type-filter {
    margin-bottom: 0;
  }

  .user-roster {
    overflow-x: auto;
  }

</style>
